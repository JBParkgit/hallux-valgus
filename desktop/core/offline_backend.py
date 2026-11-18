# -*- coding: utf-8 -*-
"""테스트 버전용 '가짜 서버' — 서버 없이 이 PC에만 저장합니다.

desktop/core/api_client.py 와 같은 이름·같은 반환 형식의 함수를 제공하고,
install() 이 api_client 모듈의 함수들을 이것으로 바꿔 끼웁니다.
화면 코드는 모두 api_client.xxx() 로 호출하므로 수정 없이 그대로 동작합니다.

- 케이스·X-ray·알고리즘 설정은 data/test_server/ 아래에 저장됩니다.
- 알림톡은 실제로 보내지 않고, 환자 리포트 링크도 만들어지지 않습니다.
- 관리자 기능·비밀번호 변경은 쓸 수 없습니다.
"""

from __future__ import annotations

import json
import os
import secrets
from datetime import datetime
from typing import Any, Optional

from desktop.core import api_client
from desktop.core.paths import data_dir

ApiError = api_client.ApiError

TEST_DOCTOR_ID = "test-doctor"
REPORT_PLACEHOLDER = "(테스트 버전 — 환자 리포트가 만들어지지 않습니다)"
REQUIRED_ON_CREATE = ("patientName", "patientBirth", "patientPhone", "patientRegNo", "patientAge")

_doctor: dict | None = None


# ── storage ─────────────────────────────────────────────────────────


def _dir(*parts: str) -> str:
    return data_dir("test_server", *parts)


def _cases_path() -> str:
    return os.path.join(_dir(), "cases.json")


def _load_cases() -> dict[str, dict]:
    try:
        with open(_cases_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def _save_cases(cases: dict[str, dict]) -> None:
    tmp = _cases_path() + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cases, f, ensure_ascii=False, indent=1)
    os.replace(tmp, _cases_path())


def _xray_path(case_id: str) -> str:
    return os.path.join(_dir("xray"), f"{case_id}.png")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _out(row: dict) -> dict:
    """Same shape as the server's _case_out + api_client._parse_case."""
    c = dict(row)
    c["reportUrl"] = REPORT_PLACEHOLDER
    c["hasXray"] = os.path.exists(_xray_path(row["id"]))
    for f in ("createdAt", "updatedAt", "alimtalkSentAt"):
        c[f] = api_client.parse_time(c.get(f))
    return c


def _require_login() -> dict:
    if not _doctor:
        raise ApiError("로그인이 필요합니다.", 401)
    return _doctor


def _get_row(case_id: str) -> dict:
    row = _load_cases().get(case_id)
    if row is None:
        raise ApiError("케이스를 찾을 수 없습니다.", 404)
    return row


# ── auth ────────────────────────────────────────────────────────────


def login(username: str, password: str = "") -> dict:
    """테스트 버전: 아무 아이디/비밀번호로 로그인됩니다 (아이디가 화면의 의사 이름)."""
    global _doctor
    name = (username or "").strip() or "테스트 원장"
    _doctor = {"id": TEST_DOCTOR_ID, "username": name, "name": name, "isAdmin": False}
    return _doctor


def logout() -> None:
    global _doctor
    _doctor = None


def current_doctor() -> Optional[dict]:
    return _doctor


def change_password(current: str, new: str) -> None:
    raise ApiError("테스트 버전에서는 비밀번호를 바꿀 수 없습니다.")


# ── cases ───────────────────────────────────────────────────────────


def list_cases() -> list[dict]:
    _require_login()
    rows = sorted(_load_cases().values(), key=lambda r: r.get("createdAt", ""), reverse=True)
    return [_out(r) for r in rows]


def get_case(case_id: str) -> dict:
    _require_login()
    return _out(_get_row(case_id))


def create_case(data: dict[str, Any]) -> dict:
    doctor = _require_login()
    missing = [f for f in REQUIRED_ON_CREATE if data.get(f) in (None, "")]
    if missing:
        raise ApiError(f"필수 항목 누락: {', '.join(missing)}", 400)
    cases = _load_cases()
    case_id = "t" + secrets.token_hex(8)
    now = _now()
    row = {
        "hypermobility": False, "jointCongruency": "congruent", "osteoarthritis": "none",
        "previousSurgery": False, "alimtalkSent": False, "alimtalkSentAt": None,
        **data,
        "id": case_id, "reportHash": secrets.token_hex(8),
        "doctorId": doctor["id"], "doctorName": doctor["name"],
        "createdAt": now, "updatedAt": now,
    }
    cases[case_id] = row
    _save_cases(cases)
    return _out(row)


def update_case(case_id: str, data: dict[str, Any]) -> dict:
    _require_login()
    cases = _load_cases()
    if case_id not in cases:
        raise ApiError("케이스를 찾을 수 없습니다.", 404)
    protected = {"id", "reportHash", "doctorId", "doctorName", "createdAt"}
    cases[case_id].update({k: v for k, v in data.items() if k not in protected})
    cases[case_id]["updatedAt"] = _now()
    _save_cases(cases)
    return _out(cases[case_id])


def delete_case(case_id: str) -> None:
    _require_login()
    cases = _load_cases()
    if cases.pop(case_id, None) is None:
        raise ApiError("케이스를 찾을 수 없습니다.", 404)
    _save_cases(cases)
    try:
        os.remove(_xray_path(case_id))
    except FileNotFoundError:
        pass


def upload_xray(case_id: str, image_bytes: bytes) -> None:
    _require_login()
    _get_row(case_id)
    with open(_xray_path(case_id), "wb") as f:
        f.write(image_bytes)


def download_xray(case_id: str) -> Optional[bytes]:
    _require_login()
    try:
        with open(_xray_path(case_id), "rb") as f:
            return f.read()
    except FileNotFoundError:
        return None


def send_alimtalk(case_id: str) -> str:
    _require_login()
    cases = _load_cases()
    if case_id not in cases:
        raise ApiError("케이스를 찾을 수 없습니다.", 404)
    cases[case_id]["alimtalkSent"] = True
    cases[case_id]["alimtalkSentAt"] = _now()
    _save_cases(cases)
    return "테스트 버전이라 실제로 발송하지 않았습니다. (발송 완료로만 표시됩니다)"


# ── per-doctor algorithm settings ───────────────────────────────────


def get_algorithm_config() -> Optional[dict]:
    _require_login()
    try:
        with open(os.path.join(_dir(), "algorithm_config.json"), "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def put_algorithm_config(config: dict) -> None:
    _require_login()
    with open(os.path.join(_dir(), "algorithm_config.json"), "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


# ── admin: 테스트 버전에서는 사용 불가 ──────────────────────────────


def is_admin() -> bool:
    return False


def _no_admin(*_a: Any, **_k: Any) -> Any:
    raise ApiError("테스트 버전에서는 관리자 기능을 쓸 수 없습니다.", 403)


_ADMIN_FUNCS = (
    "admin_list_users", "admin_create_user", "admin_update_user", "admin_reset_password",
    "admin_delete_user", "admin_transfer_cases", "admin_change_owner", "admin_delete_case",
    "admin_export_csv", "admin_status",
)


def install() -> None:
    """api_client 의 서버 호출 함수를 이 모듈의 함수로 바꿔 끼운다."""
    for name in (
        "login", "logout", "current_doctor", "change_password",
        "list_cases", "get_case", "create_case", "update_case", "delete_case",
        "upload_xray", "download_xray", "send_alimtalk",
        "get_algorithm_config", "put_algorithm_config", "is_admin",
    ):
        setattr(api_client, name, globals()[name])
    for name in _ADMIN_FUNCS:
        setattr(api_client, name, _no_admin)
    # 실수로 남은 직접 호출도 서버로 나가지 않도록 막는다
    def _blocked(*_a: Any, **_k: Any) -> Any:
        raise ApiError("테스트 버전은 서버에 연결하지 않습니다.")
    api_client._request = _blocked  # type: ignore[attr-defined]
