"""Hallux valgus measurement API (FastAPI).

All endpoints live under /api/hv. Rules:
- Every logged-in doctor can READ every case.
- Only the doctor who created a case can MODIFY it (update, delete, X-ray,
  Alimtalk). This is enforced here, on the server.
- Admins additionally manage accounts and can delete / reassign any case
  (see admin.py) — they still cannot edit another doctor's measurements.
- The report endpoints are public but need the unguessable reportHash.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from hv_server import alimtalk, config, db, security
from hv_server.deps import current_doctor

app = FastAPI(title="Hallux Valgus API", docs_url=None, redoc_url=None, openapi_url=None)

API = "/api/hv"

# Fields a client may write on a case. doctorId / reportHash / alimtalk* /
# image fields are controlled by the server only.
WRITABLE_FIELDS = {
    "patientName", "patientBirth", "patientPhone", "patientRegNo", "patientAge",
    "hvaAngle", "imaAngle", "dmaaAngle", "painDuration", "hypermobility",
    "jointCongruency", "osteoarthritis", "previousSurgery", "previousSurgeryNote",
    "clinicalNotes", "severity", "algorithmResult", "algorithmReason",
    "finalDecision", "overrideReason", "angleData",
}
REQUIRED_ON_CREATE = ("patientName", "patientBirth", "patientPhone", "patientRegNo", "patientAge")

# Fields hidden from the public report endpoint
REPORT_HIDDEN = {"patientPhone", "patientRegNo", "doctorId", "xrayImageUrl", "annotatedImageUrl"}

_IMAGE_MAGIC = {b"\x89PNG\r\n\x1a\n": "image/png", b"\xff\xd8\xff": "image/jpeg"}


# ── helpers ─────────────────────────────────────────────────────────


def _jsonable(row: dict) -> dict:
    """DB timestamps are naive UTC → send them with an explicit +00:00."""
    out = {}
    for k, v in row.items():
        if isinstance(v, datetime) and v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        out[k] = v.isoformat() if isinstance(v, (datetime, date)) else v
    return out


def _case_out(row: dict) -> dict:
    out = _jsonable(row)
    out["reportUrl"] = f"{config.REPORT_BASE_URL}/{row['reportHash']}"
    out["hasXray"] = _xray_path(row["id"]).exists()
    return out


def _xray_path(case_id: str):
    return config.XRAY_DIR / f"{case_id}.img"


def _clean_fields(data: dict[str, Any]) -> dict[str, Any]:
    fields = {k: v for k, v in data.items() if k in WRITABLE_FIELDS}
    if "angleData" in fields and not isinstance(fields["angleData"], (str, type(None))):
        fields["angleData"] = json.dumps(fields["angleData"], ensure_ascii=False)
    return fields


def _get_case_row(case_id: str) -> dict:
    with db.cursor() as cur:
        cur.execute(
            'SELECT c.*, d.name AS "doctorName" FROM "Case" c '
            'JOIN "Doctor" d ON d.id = c."doctorId" WHERE c.id = %s',
            (case_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "케이스를 찾을 수 없습니다.")
    return dict(row)


def _require_owner(row: dict, doctor: dict) -> None:
    if row["doctorId"] != doctor["id"]:
        raise HTTPException(403, "본인이 작성한 케이스만 수정할 수 있습니다.")


# ── auth ────────────────────────────────────────────────────────────




class LoginIn(BaseModel):
    username: str
    password: str


@app.get(f"{API}/health")
def health() -> dict:
    with db.cursor() as cur:
        cur.execute("SELECT 1")
    return {"status": "ok"}


@app.post(f"{API}/login")
def login(body: LoginIn) -> dict:
    with db.cursor() as cur:
        cur.execute(
            'SELECT id, username, name, hospital, "passwordHash", "isActive", "isAdmin" '
            'FROM "Doctor" WHERE username = %s',
            (body.username.strip(),),
        )
        row = cur.fetchone()
    if not row or not security.check_password(body.password, row["passwordHash"]):
        raise HTTPException(401, "아이디 또는 비밀번호가 올바르지 않습니다.")
    if not row["isActive"]:
        raise HTTPException(403, "사용이 중지된 계정입니다. 관리자에게 문의하세요.")
    token = security.create_session(row["id"])
    with db.cursor() as cur:
        cur.execute('UPDATE "Doctor" SET "lastLoginAt" = NOW() WHERE id = %s', (row["id"],))
    doctor = {k: row[k] for k in ("id", "username", "name", "hospital", "isAdmin")}
    return {"token": token, "doctor": doctor}


@app.post(f"{API}/logout")
def logout(doctor: dict = Depends(current_doctor)) -> dict:
    security.delete_session(doctor["_token"])
    return {"status": "ok"}


@app.get(f"{API}/me")
def me(doctor: dict = Depends(current_doctor)) -> dict:
    return {k: doctor[k] for k in ("id", "username", "name", "hospital", "isAdmin")}


class PasswordIn(BaseModel):
    current_password: str
    new_password: str


@app.post(f"{API}/me/password")
def change_password(body: PasswordIn, doctor: dict = Depends(current_doctor)) -> dict:
    if not body.new_password:
        raise HTTPException(400, "새 비밀번호를 입력해 주세요.")
    with db.cursor() as cur:
        cur.execute('SELECT "passwordHash" FROM "Doctor" WHERE id = %s', (doctor["id"],))
        row = cur.fetchone()
        if not row or not security.check_password(body.current_password, row["passwordHash"]):
            raise HTTPException(400, "현재 비밀번호가 올바르지 않습니다.")
        cur.execute(
            'UPDATE "Doctor" SET "passwordHash" = %s WHERE id = %s',
            (security.hash_password(body.new_password), doctor["id"]),
        )
        # Log out every other PC; keep this session
        cur.execute(
            'DELETE FROM "Session" WHERE "doctorId" = %s AND "tokenHash" <> %s',
            (doctor["id"], security.token_hash(doctor["_token"])),
        )
    return {"status": "ok"}


# ── algorithm settings (per doctor) ─────────────────────────────────


@app.get(f"{API}/me/algorithm-config")
def get_algorithm_config(doctor: dict = Depends(current_doctor)) -> dict:
    with db.cursor() as cur:
        cur.execute('SELECT config FROM "AlgorithmConfig" WHERE "doctorId" = %s', (doctor["id"],))
        row = cur.fetchone()
    return {"config": json.loads(row["config"]) if row else None}


@app.put(f"{API}/me/algorithm-config")
def put_algorithm_config(body: dict, doctor: dict = Depends(current_doctor)) -> dict:
    cfg = body.get("config")
    if not isinstance(cfg, dict):
        raise HTTPException(400, "config 형식이 올바르지 않습니다.")
    with db.cursor() as cur:
        cur.execute(
            'INSERT INTO "AlgorithmConfig" ("doctorId", config, "updatedAt") VALUES (%s, %s, NOW()) '
            'ON CONFLICT ("doctorId") DO UPDATE SET config = EXCLUDED.config, "updatedAt" = NOW()',
            (doctor["id"], json.dumps(cfg, ensure_ascii=False)),
        )
    return {"status": "ok"}


# ── cases ───────────────────────────────────────────────────────────


@app.get(f"{API}/cases")
def list_cases(doctor: dict = Depends(current_doctor)) -> list[dict]:
    with db.cursor() as cur:
        cur.execute(
            'SELECT c.*, d.name AS "doctorName" FROM "Case" c '
            'JOIN "Doctor" d ON d.id = c."doctorId" ORDER BY c."createdAt" DESC'
        )
        rows = cur.fetchall()
    return [_case_out(dict(r)) for r in rows]


@app.get(f"{API}/cases/{{case_id}}")
def get_case(case_id: str, doctor: dict = Depends(current_doctor)) -> dict:
    return _case_out(_get_case_row(case_id))


@app.post(f"{API}/cases", status_code=201)
def create_case(body: dict, doctor: dict = Depends(current_doctor)) -> dict:
    fields = _clean_fields(body)
    missing = [f for f in REQUIRED_ON_CREATE if fields.get(f) in (None, "")]
    if missing:
        raise HTTPException(400, f"필수 항목 누락: {', '.join(missing)}")
    case_id = security.new_id()
    fields.update(id=case_id, reportHash=security.new_report_hash(), doctorId=doctor["id"])
    cols = ", ".join(f'"{k}"' for k in fields)
    marks = ", ".join(["%s"] * len(fields))
    with db.cursor() as cur:
        cur.execute(f'INSERT INTO "Case" ({cols}) VALUES ({marks})', list(fields.values()))
    return _case_out(_get_case_row(case_id))


@app.put(f"{API}/cases/{{case_id}}")
def update_case(case_id: str, body: dict, doctor: dict = Depends(current_doctor)) -> dict:
    row = _get_case_row(case_id)
    _require_owner(row, doctor)
    fields = _clean_fields(body)
    if fields:
        sets = ", ".join(f'"{k}" = %s' for k in fields)
        with db.cursor() as cur:
            cur.execute(
                f'UPDATE "Case" SET {sets}, "updatedAt" = NOW() WHERE id = %s AND "doctorId" = %s',
                [*fields.values(), case_id, doctor["id"]],
            )
    return _case_out(_get_case_row(case_id))


@app.delete(f"{API}/cases/{{case_id}}")
def delete_case(case_id: str, doctor: dict = Depends(current_doctor)) -> dict:
    row = _get_case_row(case_id)
    _require_owner(row, doctor)
    with db.cursor() as cur:
        cur.execute('DELETE FROM "Case" WHERE id = %s AND "doctorId" = %s', (case_id, doctor["id"]))
    _xray_path(case_id).unlink(missing_ok=True)
    return {"status": "ok"}


# ── X-ray image ─────────────────────────────────────────────────────


@app.put(f"{API}/cases/{{case_id}}/xray")
async def put_xray(case_id: str, request: Request, doctor: dict = Depends(current_doctor)) -> dict:
    row = _get_case_row(case_id)
    _require_owner(row, doctor)
    data = await request.body()
    if not data:
        raise HTTPException(400, "이미지가 비어 있습니다.")
    if len(data) > config.MAX_XRAY_BYTES:
        raise HTTPException(413, "이미지가 너무 큽니다.")
    if not any(data.startswith(m) for m in _IMAGE_MAGIC):
        raise HTTPException(400, "PNG 또는 JPEG 이미지만 저장할 수 있습니다.")
    config.XRAY_DIR.mkdir(parents=True, exist_ok=True)
    tmp = _xray_path(case_id).with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(_xray_path(case_id))
    return {"status": "ok", "bytes": len(data)}


def _xray_response(case_id: str) -> Response:
    path = _xray_path(case_id)
    if not path.exists():
        raise HTTPException(404, "X-ray 이미지가 없습니다.")
    with open(path, "rb") as f:
        head = f.read(8)
    media = next((t for m, t in _IMAGE_MAGIC.items() if head.startswith(m)), "application/octet-stream")
    return FileResponse(path, media_type=media, headers={"Cache-Control": "private, max-age=300"})


@app.get(f"{API}/cases/{{case_id}}/xray")
def get_xray(case_id: str, doctor: dict = Depends(current_doctor)) -> Response:
    _get_case_row(case_id)
    return _xray_response(case_id)


# ── Alimtalk ────────────────────────────────────────────────────────


@app.post(f"{API}/cases/{{case_id}}/alimtalk")
def send_alimtalk(case_id: str, doctor: dict = Depends(current_doctor)) -> dict:
    row = _get_case_row(case_id)
    _require_owner(row, doctor)
    ok, message = alimtalk.send(
        row["patientPhone"], row["patientName"], f"{config.REPORT_BASE_URL}/{row['reportHash']}",
    )
    if not ok:
        raise HTTPException(502, message)
    with db.cursor() as cur:
        cur.execute(
            'UPDATE "Case" SET "alimtalkSent" = TRUE, "alimtalkSentAt" = NOW() WHERE id = %s',
            (case_id,),
        )
    return {"status": "ok", "message": message}


# ── public report (for the patient-facing web page) ─────────────────


def _case_by_hash(report_hash: str) -> dict:
    with db.cursor() as cur:
        cur.execute(
            'SELECT c.*, d.name AS "doctorName", d.hospital AS "hospital" FROM "Case" c '
            'JOIN "Doctor" d ON d.id = c."doctorId" WHERE c."reportHash" = %s',
            (report_hash,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(404, "리포트를 찾을 수 없습니다.")
    return dict(row)


@app.get(f"{API}/report/{{report_hash}}")
def get_report(report_hash: str) -> dict:
    row = _case_by_hash(report_hash)
    out = {k: v for k, v in _jsonable(row).items() if k not in REPORT_HIDDEN}
    out["hasXray"] = _xray_path(row["id"]).exists()
    return out


@app.get(f"{API}/report/{{report_hash}}/xray")
def get_report_xray(report_hash: str) -> Response:
    return _xray_response(_case_by_hash(report_hash)["id"])


from hv_server import admin  # noqa: E402

app.include_router(admin.router)


@app.exception_handler(HTTPException)
def _http_error(_: Request, exc: HTTPException) -> JSONResponse:
    # Korean message in "detail" for the desktop client to show as-is
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
