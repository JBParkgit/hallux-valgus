# -*- coding: utf-8 -*-
"""Client for the hallux valgus server API (Vultr).

The desktop app no longer connects to the database directly: it logs in to the
server and every read/write goes through the API, which enforces
"everyone can view, only the author can modify".

Server address: HV_API_URL in the .env next to the app (or exe), e.g.
    HV_API_URL=https://hv.example.co.kr
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Optional

import requests
from dotenv import load_dotenv

from desktop.core.paths import app_root

load_dotenv(os.path.join(app_root(), ".env"))

API_URL = os.getenv("HV_API_URL", "").rstrip("/")
TIMEOUT = 20
UPLOAD_TIMEOUT = 90

_DATE_FIELDS = ("createdAt", "updatedAt", "alimtalkSentAt")

_session = requests.Session()
_token: str | None = None
_doctor: dict | None = None


class ApiError(Exception):
    """Error with a user-facing (Korean) message."""

    def __init__(self, message: str, status: int = 0) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


# ── low level ───────────────────────────────────────────────────────


def _url(path: str) -> str:
    if not API_URL:
        raise ApiError("서버 주소(HV_API_URL)가 설정되지 않았습니다. .env 파일을 확인하세요.")
    return f"{API_URL}/api/hv{path}"


def _request(method: str, path: str, *, auth: bool = True, timeout: float = TIMEOUT, **kw) -> requests.Response:
    headers = kw.pop("headers", {})
    if auth:
        if not _token:
            raise ApiError("로그인이 필요합니다.", 401)
        headers["Authorization"] = f"Bearer {_token}"
    try:
        res = _session.request(method, _url(path), headers=headers, timeout=timeout, **kw)
    except requests.exceptions.Timeout:
        raise ApiError("서버 응답 시간이 초과되었습니다. 잠시 후 다시 시도하세요.")
    except requests.exceptions.ConnectionError:
        raise ApiError(f"서버에 연결할 수 없습니다.\n({API_URL})\n인터넷 연결을 확인하세요.")
    if not res.ok:
        try:
            detail = res.json().get("detail")
        except ValueError:
            detail = None
        if not isinstance(detail, str):
            detail = f"서버 오류 (HTTP {res.status_code})"
        raise ApiError(detail, res.status_code)
    return res


def parse_time(v: Any) -> Any:
    """ISO string from the server (UTC) → naive datetime in this PC's local time."""
    if not isinstance(v, str):
        return v
    try:
        dt = datetime.fromisoformat(v)
    except ValueError:
        return v
    return dt.astimezone().replace(tzinfo=None) if dt.tzinfo else dt


def _parse_case(c: dict) -> dict:
    for f in _DATE_FIELDS:
        c[f] = parse_time(c.get(f))
    return c


# ── auth ────────────────────────────────────────────────────────────


def login(username: str, password: str) -> dict:
    global _token, _doctor
    res = _request("POST", "/login", auth=False, json={"username": username, "password": password})
    data = res.json()
    _token, _doctor = data["token"], data["doctor"]
    return _doctor


def logout() -> None:
    global _token, _doctor
    if _token:
        try:
            _request("POST", "/logout", timeout=5)
        except ApiError:
            pass
    _token, _doctor = None, None


def current_doctor() -> Optional[dict]:
    return _doctor


def change_password(current: str, new: str) -> None:
    _request("POST", "/me/password", json={"current_password": current, "new_password": new})


# ── cases ───────────────────────────────────────────────────────────


def list_cases() -> list[dict]:
    return [_parse_case(c) for c in _request("GET", "/cases").json()]


def get_case(case_id: str) -> dict:
    return _parse_case(_request("GET", f"/cases/{case_id}").json())


def create_case(data: dict[str, Any]) -> dict:
    return _parse_case(_request("POST", "/cases", json=data).json())


def update_case(case_id: str, data: dict[str, Any]) -> dict:
    return _parse_case(_request("PUT", f"/cases/{case_id}", json=data).json())


def delete_case(case_id: str) -> None:
    _request("DELETE", f"/cases/{case_id}")


def upload_xray(case_id: str, image_bytes: bytes) -> None:
    _request(
        "PUT", f"/cases/{case_id}/xray", data=image_bytes, timeout=UPLOAD_TIMEOUT,
        headers={"Content-Type": "application/octet-stream"},
    )


def download_xray(case_id: str) -> Optional[bytes]:
    try:
        return _request("GET", f"/cases/{case_id}/xray", timeout=UPLOAD_TIMEOUT).content
    except ApiError as e:
        if e.status == 404:
            return None
        raise


def send_alimtalk(case_id: str) -> str:
    return _request("POST", f"/cases/{case_id}/alimtalk").json().get("message", "발송 완료")


# ── per-doctor algorithm settings ───────────────────────────────────


def get_algorithm_config() -> Optional[dict]:
    return _request("GET", "/me/algorithm-config").json().get("config")


def put_algorithm_config(config: dict) -> None:
    _request("PUT", "/me/algorithm-config", json={"config": config})


# ── admin (관리자 전용) ──────────────────────────────────────────────


def is_admin() -> bool:
    return bool(_doctor and _doctor.get("isAdmin"))


def admin_list_users() -> list[dict]:
    users = _request("GET", "/admin/users").json()
    for u in users:
        for f in ("createdAt", "lastLoginAt"):
            u[f] = parse_time(u.get(f))
    return users


def admin_create_user(username: str, name: str, is_admin: bool = False) -> dict:
    """Returns {"id", "username", "name", "tempPassword"}."""
    return _request("POST", "/admin/users", json={"username": username, "name": name, "isAdmin": is_admin}).json()


def admin_update_user(doctor_id: str, **fields: Any) -> None:
    _request("PUT", f"/admin/users/{doctor_id}", json=fields)


def admin_reset_password(doctor_id: str) -> str:
    return _request("POST", f"/admin/users/{doctor_id}/reset-password").json()["tempPassword"]


def admin_delete_user(doctor_id: str) -> None:
    _request("DELETE", f"/admin/users/{doctor_id}")


def admin_transfer_cases(from_id: str, to_id: str) -> int:
    return _request("POST", f"/admin/users/{from_id}/transfer-cases", json={"toDoctorId": to_id}).json()["moved"]


def admin_change_owner(case_id: str, doctor_id: str) -> None:
    _request("PUT", f"/admin/cases/{case_id}/owner", json={"doctorId": doctor_id})


def admin_delete_case(case_id: str) -> None:
    _request("DELETE", f"/admin/cases/{case_id}")


def admin_export_csv() -> bytes:
    return _request("GET", "/admin/export.csv", timeout=UPLOAD_TIMEOUT).content


def admin_status() -> dict:
    return _request("GET", "/admin/status").json()
