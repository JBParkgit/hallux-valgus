"""Admin API (/api/hv/admin/*): account management and data management.

Admins can:
- create accounts (temporary password is generated and returned once),
  reset passwords, rename, activate/deactivate, grant/revoke admin,
  delete accounts that have no cases
- move every case of one doctor to another (e.g. when someone leaves)
- delete any case, change any case's author
- export all cases as CSV, see server status

Admins can NOT edit another doctor's measurements / clinical content.

Guards against locking everyone out: an admin cannot deactivate or demote
themselves, and the last active admin can never be removed.
"""

from __future__ import annotations

import csv
import io
import json
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from hv_server import config, db, security
from hv_server.deps import require_admin

router = APIRouter(prefix="/api/hv/admin", dependencies=[Depends(require_admin)])

BACKUP_DIR = Path("/var/backups/hv")


KST = timezone(timedelta(hours=9))


def _iso(v):
    if isinstance(v, datetime) and v.tzinfo is None:
        v = v.replace(tzinfo=timezone.utc)  # DB stores naive UTC
    return v.isoformat() if isinstance(v, datetime) else v


def _kst(v) -> str:
    """Naive-UTC DB timestamp → 'YYYY-MM-DD HH:MM' in Korean time (for CSV)."""
    if not isinstance(v, datetime):
        return ""
    return v.replace(tzinfo=timezone.utc).astimezone(KST).strftime("%Y-%m-%d %H:%M")


def _doctor_row(doctor_id: str) -> dict:
    with db.cursor() as cur:
        cur.execute('SELECT * FROM "Doctor" WHERE id = %s', (doctor_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "사용자를 찾을 수 없습니다.")
    return dict(row)


def _active_admin_count(cur) -> int:
    cur.execute('SELECT COUNT(*) AS n FROM "Doctor" WHERE "isAdmin" AND "isActive"')
    return cur.fetchone()["n"]


def _kill_sessions(cur, doctor_id: str) -> None:
    cur.execute('DELETE FROM "Session" WHERE "doctorId" = %s', (doctor_id,))


# ── users ───────────────────────────────────────────────────────────


@router.get("/users")
def list_users() -> list[dict]:
    with db.cursor() as cur:
        cur.execute(
            '''
            SELECT d.id, d.username, d.name, d.hospital, d."isActive", d."isAdmin",
                   d."createdAt", d."lastLoginAt", COUNT(c.id) AS "caseCount"
            FROM "Doctor" d LEFT JOIN "Case" c ON c."doctorId" = d.id
            GROUP BY d.id
            ORDER BY d."isActive" DESC, d."createdAt"
            '''
        )
        rows = cur.fetchall()
    return [{k: _iso(v) for k, v in r.items()} for r in rows]


class UserCreate(BaseModel):
    username: str
    name: str
    password: Optional[str] = None
    isAdmin: bool = False


@router.post("/users", status_code=201)
def create_user(body: UserCreate) -> dict:
    username, name = body.username.strip(), body.name.strip()
    if not username or not name:
        raise HTTPException(400, "아이디와 이름을 입력해 주세요.")
    if any(ch.isspace() for ch in username):
        raise HTTPException(400, "아이디에는 공백을 쓸 수 없습니다.")
    password = body.password or security.new_temp_password()
    with db.cursor() as cur:
        cur.execute('SELECT 1 FROM "Doctor" WHERE username = %s', (username,))
        if cur.fetchone():
            raise HTTPException(409, f"이미 있는 아이디입니다: {username}")
        new_id = security.new_id()
        cur.execute(
            'INSERT INTO "Doctor" (id, username, "passwordHash", name, "isAdmin") VALUES (%s,%s,%s,%s,%s)',
            (new_id, username, security.hash_password(password), name, body.isAdmin),
        )
    # The temporary password is returned only here, once
    return {"id": new_id, "username": username, "name": name, "tempPassword": password}


class UserUpdate(BaseModel):
    name: Optional[str] = None
    isActive: Optional[bool] = None
    isAdmin: Optional[bool] = None


@router.put("/users/{doctor_id}")
def update_user(doctor_id: str, body: UserUpdate, admin: dict = Depends(require_admin)) -> dict:
    target = _doctor_row(doctor_id)
    is_self = doctor_id == admin["id"]
    if is_self and body.isActive is False:
        raise HTTPException(400, "자기 자신은 사용 중지할 수 없습니다.")
    if is_self and body.isAdmin is False:
        raise HTTPException(400, "자기 자신의 관리자 권한은 해제할 수 없습니다.")

    sets, vals = [], []
    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(400, "이름을 입력해 주세요.")
        sets.append('name = %s'); vals.append(body.name.strip())
    if body.isActive is not None:
        sets.append('"isActive" = %s'); vals.append(body.isActive)
    if body.isAdmin is not None:
        sets.append('"isAdmin" = %s'); vals.append(body.isAdmin)
    if not sets:
        return {"status": "ok"}

    with db.cursor() as cur:
        cur.execute(f'UPDATE "Doctor" SET {", ".join(sets)} WHERE id = %s', [*vals, doctor_id])
        if _active_admin_count(cur) == 0:
            raise HTTPException(400, "활성 관리자가 최소 1명은 있어야 합니다.")  # rolls back
        if body.isActive is False and target["isActive"]:
            _kill_sessions(cur, doctor_id)
    return {"status": "ok"}


@router.post("/users/{doctor_id}/reset-password")
def reset_password(doctor_id: str) -> dict:
    _doctor_row(doctor_id)
    password = security.new_temp_password()
    with db.cursor() as cur:
        cur.execute(
            'UPDATE "Doctor" SET "passwordHash" = %s WHERE id = %s',
            (security.hash_password(password), doctor_id),
        )
        _kill_sessions(cur, doctor_id)
    return {"tempPassword": password}


@router.delete("/users/{doctor_id}")
def delete_user(doctor_id: str, admin: dict = Depends(require_admin)) -> dict:
    if doctor_id == admin["id"]:
        raise HTTPException(400, "자기 자신은 삭제할 수 없습니다.")
    _doctor_row(doctor_id)
    with db.cursor() as cur:
        cur.execute('SELECT COUNT(*) AS n FROM "Case" WHERE "doctorId" = %s', (doctor_id,))
        if cur.fetchone()["n"]:
            raise HTTPException(
                400, "케이스가 있는 계정은 삭제할 수 없습니다. 케이스를 이관하거나 사용 중지하세요."
            )
        cur.execute('DELETE FROM "Doctor" WHERE id = %s', (doctor_id,))
        if _active_admin_count(cur) == 0:
            raise HTTPException(400, "활성 관리자가 최소 1명은 있어야 합니다.")
    return {"status": "ok"}


class Transfer(BaseModel):
    toDoctorId: str


@router.post("/users/{doctor_id}/transfer-cases")
def transfer_cases(doctor_id: str, body: Transfer) -> dict:
    _doctor_row(doctor_id)
    _doctor_row(body.toDoctorId)
    if doctor_id == body.toDoctorId:
        raise HTTPException(400, "같은 사용자에게는 이관할 수 없습니다.")
    with db.cursor() as cur:
        cur.execute(
            'UPDATE "Case" SET "doctorId" = %s, "updatedAt" = NOW() WHERE "doctorId" = %s',
            (body.toDoctorId, doctor_id),
        )
        moved = cur.rowcount
    return {"moved": moved}


# ── cases ───────────────────────────────────────────────────────────


class OwnerChange(BaseModel):
    doctorId: str


@router.put("/cases/{case_id}/owner")
def change_owner(case_id: str, body: OwnerChange) -> dict:
    _doctor_row(body.doctorId)
    with db.cursor() as cur:
        cur.execute(
            'UPDATE "Case" SET "doctorId" = %s, "updatedAt" = NOW() WHERE id = %s',
            (body.doctorId, case_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "케이스를 찾을 수 없습니다.")
    return {"status": "ok"}


@router.delete("/cases/{case_id}")
def delete_any_case(case_id: str) -> dict:
    with db.cursor() as cur:
        cur.execute('DELETE FROM "Case" WHERE id = %s', (case_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "케이스를 찾을 수 없습니다.")
    (config.XRAY_DIR / f"{case_id}.img").unlink(missing_ok=True)
    return {"status": "ok"}


_SEV_KR = {"mild": "경증", "moderate": "중등도", "severe": "중증"}


def _side(angle_data: dict, side: str) -> dict:
    s = angle_data.get(f"{side}_surgery") or {}
    a = s.get("angles") or {}
    return {
        "hva": a.get("hva"), "ima": a.get("ima"), "dmaa": a.get("dmaa"),
        "severity": _SEV_KR.get(s.get("severity") or "", s.get("severity") or ""),
        "recommend": " + ".join(x for x in (s.get("algorithm_result"), s.get("addon_surgery")) if x),
        "final": s.get("final_decision") or "",
    }


def _num(v):
    return "" if v is None else round(v, 1)


@router.get("/export.csv")
def export_csv() -> Response:
    with db.cursor() as cur:
        cur.execute(
            'SELECT c.*, d.name AS "doctorName", d.username AS "doctorUsername" FROM "Case" c '
            'JOIN "Doctor" d ON d.id = c."doctorId" ORDER BY c."createdAt"'
        )
        rows = cur.fetchall()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "케이스ID", "작성일시", "수정일시", "작성자", "작성자ID",
        "환자명", "생년월일", "나이", "등록번호", "전화번호",
        "좌 HVA", "좌 IMA", "좌 DMAA", "좌 중증도", "좌 추천수술", "좌 최종수술",
        "우 HVA", "우 IMA", "우 DMAA", "우 중증도", "우 추천수술", "우 최종수술",
        "메모", "알림톡발송", "알림톡발송일시", "X-ray",
    ])
    for r in rows:
        try:
            ad = json.loads(r["angleData"] or "{}")
        except (TypeError, ValueError):
            ad = {}
        left, right = _side(ad, "left"), _side(ad, "right")
        w.writerow([
            r["id"], _kst(r["createdAt"]), _kst(r["updatedAt"]),
            r["doctorName"], r["doctorUsername"],
            r["patientName"], r["patientBirth"], r["patientAge"], r["patientRegNo"], r["patientPhone"],
            _num(left["hva"]), _num(left["ima"]), _num(left["dmaa"]), left["severity"], left["recommend"], left["final"],
            _num(right["hva"]), _num(right["ima"]), _num(right["dmaa"]), right["severity"], right["recommend"], right["final"],
            r["clinicalNotes"] or "", "Y" if r["alimtalkSent"] else "N",
            _kst(r["alimtalkSentAt"]),
            "Y" if (config.XRAY_DIR / f'{r["id"]}.img').exists() else "N",
        ])
    # UTF-8 BOM so Excel opens Korean text correctly
    data = ("﻿" + buf.getvalue()).encode("utf-8")
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    return Response(
        data,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="hallux-cases-{stamp}.csv"'},
    )


@router.get("/status")
def status() -> dict:
    with db.cursor() as cur:
        cur.execute('SELECT COUNT(*) AS n FROM "Case"')
        cases = cur.fetchone()["n"]
        cur.execute('SELECT COUNT(*) AS n, COUNT(*) FILTER (WHERE "isActive") AS active FROM "Doctor"')
        users = cur.fetchone()
        cur.execute("SELECT pg_database_size(current_database()) AS b")
        db_bytes = cur.fetchone()["b"]

    xray_files = list(config.XRAY_DIR.glob("*.img")) if config.XRAY_DIR.exists() else []
    disk = shutil.disk_usage(config.XRAY_DIR if config.XRAY_DIR.exists() else "/")

    last_backup = None
    try:
        dumps = sorted(BACKUP_DIR.glob("hv-db-*.dump"), key=lambda p: p.stat().st_mtime)
        if dumps:
            last_backup = datetime.fromtimestamp(dumps[-1].stat().st_mtime, tz=timezone.utc).isoformat()
    except OSError:
        pass

    return {
        "cases": cases,
        "users": users["n"],
        "activeUsers": users["active"],
        "xrayCount": len(xray_files),
        "xrayBytes": sum(p.stat().st_size for p in xray_files),
        "dbBytes": db_bytes,
        "diskTotal": disk.total,
        "diskFree": disk.free,
        "lastBackup": last_backup,
    }
