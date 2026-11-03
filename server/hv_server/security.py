"""Passwords, ids and login tokens."""

from __future__ import annotations

import hashlib
import secrets
import string
import time
from datetime import datetime, timedelta

import bcrypt

from hv_server import config, db


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def check_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def new_id() -> str:
    """CUID-like id (c + base36 time + 8 random chars), same shape as Prisma's."""
    n = int(time.time() * 1000)
    chars = string.digits + string.ascii_lowercase
    ts = ""
    while n:
        n, r = divmod(n, 36)
        ts = chars[r] + ts
    return "c" + ts + "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(8))


def new_temp_password(length: int = 10) -> str:
    """Readable random password (no 0/O/1/l/I) for new or reset accounts."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def new_report_hash() -> str:
    """Unguessable id for the public report link."""
    return secrets.token_urlsafe(18)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(doctor_id: str) -> str:
    token = secrets.token_urlsafe(32)
    expires = datetime.utcnow() + timedelta(hours=config.TOKEN_TTL_HOURS)
    with db.cursor() as cur:
        cur.execute('DELETE FROM "Session" WHERE "expiresAt" < NOW() AT TIME ZONE \'UTC\'')
        cur.execute(
            'INSERT INTO "Session" ("tokenHash", "doctorId", "expiresAt") VALUES (%s, %s, %s)',
            (token_hash(token), doctor_id, expires),
        )
    return token


def doctor_for_token(token: str) -> dict | None:
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT d.id, d.username, d.name, d.hospital, d."isAdmin"
            FROM "Session" s JOIN "Doctor" d ON d.id = s."doctorId"
            WHERE s."tokenHash" = %s
              AND s."expiresAt" > NOW() AT TIME ZONE 'UTC'
              AND d."isActive"
            """,
            (token_hash(token),),
        )
        row = cur.fetchone()
    return dict(row) if row else None


def delete_session(token: str) -> None:
    with db.cursor() as cur:
        cur.execute('DELETE FROM "Session" WHERE "tokenHash" = %s', (token_hash(token),))
