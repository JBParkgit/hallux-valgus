"""PostgreSQL access: connection pool and schema.

The "Doctor" / "Case" tables keep the same columns as before (Prisma schema),
so the web report keeps working against this database.
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import psycopg2
import psycopg2.extras
import psycopg2.pool

from hv_server import config

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        if not config.DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not set")
        _pool = psycopg2.pool.ThreadedConnectionPool(1, 10, dsn=config.DATABASE_URL)
    return _pool


@contextmanager
def cursor() -> Iterator[psycopg2.extras.RealDictCursor]:
    """Transaction-scoped dict cursor: commits on success, rolls back on error."""
    conn = pool().getconn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool().putconn(conn)


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS "Doctor" (
    id             TEXT PRIMARY KEY,
    username       TEXT UNIQUE NOT NULL,
    "passwordHash" TEXT NOT NULL,
    name           TEXT NOT NULL,
    hospital       TEXT NOT NULL DEFAULT '달려라병원',
    "isActive"     BOOLEAN NOT NULL DEFAULT TRUE,
    "createdAt"    TIMESTAMP NOT NULL DEFAULT NOW()
);
ALTER TABLE "Doctor" ADD COLUMN IF NOT EXISTS "isActive" BOOLEAN NOT NULL DEFAULT TRUE;
ALTER TABLE "Doctor" ADD COLUMN IF NOT EXISTS "isAdmin" BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE "Doctor" ADD COLUMN IF NOT EXISTS "lastLoginAt" TIMESTAMP;

CREATE TABLE IF NOT EXISTS "Case" (
    id                    TEXT PRIMARY KEY,
    "reportHash"          TEXT UNIQUE NOT NULL,
    "patientName"         TEXT NOT NULL,
    "patientBirth"        TEXT NOT NULL,
    "patientPhone"        TEXT NOT NULL,
    "patientRegNo"        TEXT NOT NULL,
    "patientAge"          INTEGER NOT NULL,
    "hvaAngle"            DOUBLE PRECISION,
    "imaAngle"            DOUBLE PRECISION,
    "dmaaAngle"           DOUBLE PRECISION,
    "painDuration"        TEXT,
    hypermobility         BOOLEAN NOT NULL DEFAULT FALSE,
    "jointCongruency"     TEXT NOT NULL DEFAULT 'congruent',
    osteoarthritis        TEXT NOT NULL DEFAULT 'none',
    "previousSurgery"     BOOLEAN NOT NULL DEFAULT FALSE,
    "previousSurgeryNote" TEXT,
    "clinicalNotes"       TEXT,
    severity              TEXT,
    "algorithmResult"     TEXT,
    "algorithmReason"     TEXT,
    "finalDecision"       TEXT,
    "overrideReason"      TEXT,
    "xrayImageUrl"        TEXT,
    "annotatedImageUrl"   TEXT,
    "angleData"           TEXT,
    "doctorId"            TEXT NOT NULL REFERENCES "Doctor"(id),
    "alimtalkSent"        BOOLEAN NOT NULL DEFAULT FALSE,
    "alimtalkSentAt"      TIMESTAMP,
    "createdAt"           TIMESTAMP NOT NULL DEFAULT NOW(),
    "updatedAt"           TIMESTAMP NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS "Case_doctorId_idx" ON "Case" ("doctorId");
CREATE INDEX IF NOT EXISTS "Case_createdAt_idx" ON "Case" ("createdAt" DESC);

-- Login sessions (token is stored as a SHA-256 hash only)
CREATE TABLE IF NOT EXISTS "Session" (
    "tokenHash"  TEXT PRIMARY KEY,
    "doctorId"   TEXT NOT NULL REFERENCES "Doctor"(id) ON DELETE CASCADE,
    "createdAt"  TIMESTAMP NOT NULL DEFAULT NOW(),
    "expiresAt"  TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS "Session_expiresAt_idx" ON "Session" ("expiresAt");

-- Per-doctor surgery recommendation settings (JSON)
CREATE TABLE IF NOT EXISTS "AlgorithmConfig" (
    "doctorId"   TEXT PRIMARY KEY REFERENCES "Doctor"(id) ON DELETE CASCADE,
    config       TEXT NOT NULL,
    "updatedAt"  TIMESTAMP NOT NULL DEFAULT NOW()
);
"""


def init_schema() -> None:
    with cursor() as cur:
        cur.execute(SCHEMA_SQL)
