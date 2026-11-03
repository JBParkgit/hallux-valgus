"""Request dependencies: who is calling, and are they an admin."""

from __future__ import annotations

from fastapi import Depends, Header, HTTPException

from hv_server import security


def current_doctor(authorization: str = Header(default="")) -> dict:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(401, "로그인이 필요합니다.")
    doctor = security.doctor_for_token(token)
    if not doctor:
        raise HTTPException(401, "로그인이 만료되었습니다. 다시 로그인해 주세요.")
    doctor["_token"] = token
    return doctor


def require_admin(doctor: dict = Depends(current_doctor)) -> dict:
    if not doctor.get("isAdmin"):
        raise HTTPException(403, "관리자만 사용할 수 있습니다.")
    return doctor
