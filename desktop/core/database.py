# -*- coding: utf-8 -*-
"""
PostgreSQL 데이터베이스 모듈
Neon PostgreSQL 연결 및 Doctor/Case 테이블 CRUD 작업
"""

import os
import time
import random
import string
import logging
from typing import Optional
from datetime import datetime

import bcrypt
import psycopg2
import psycopg2.pool
import psycopg2.extras
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# 프로젝트 루트의 .env 파일 로드
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

# 커넥션 풀 (모듈 레벨 싱글톤)
_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None


def generate_cuid() -> str:
    """CUID와 유사한 고유 ID 생성기.

    형식: c + 타임스탬프(36진) + 랜덤(8자)
    """
    ts_part = _to_base36(int(time.time() * 1000))
    random_part = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"c{ts_part}{random_part}"


def _to_base36(value: int) -> str:
    """정수를 36진 문자열로 변환."""
    if value == 0:
        return "0"
    chars = string.digits + string.ascii_lowercase
    result = []
    while value > 0:
        result.append(chars[value % 36])
        value //= 36
    return "".join(reversed(result))


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    """커넥션 풀 반환 (lazy 초기화)."""
    global _pool
    if _pool is None or _pool.closed:
        database_url = os.getenv("DATABASE_URL")
        if not database_url:
            raise RuntimeError("DATABASE_URL 환경 변수가 설정되지 않았습니다. .env 파일을 확인하세요.")
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=database_url,
        )
        logger.info("데이터베이스 커넥션 풀 생성 완료")
    return _pool


def _get_conn():
    """커넥션 풀에서 연결 획득."""
    return _get_pool().getconn()


def _put_conn(conn):
    """커넥션 풀에 연결 반환."""
    _get_pool().putconn(conn)


# ---------------------------------------------------------------------------
# 스키마 초기화
# ---------------------------------------------------------------------------

_CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS "Doctor" (
    id            TEXT PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL,
    "passwordHash" TEXT NOT NULL,
    name          TEXT NOT NULL,
    hospital      TEXT NOT NULL DEFAULT '달려라병원',
    "createdAt"   TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS "Case" (
    id                  TEXT PRIMARY KEY,
    "reportHash"        TEXT UNIQUE NOT NULL,
    "patientName"       TEXT NOT NULL,
    "patientBirth"      TEXT NOT NULL,
    "patientPhone"      TEXT NOT NULL,
    "patientRegNo"      TEXT NOT NULL,
    "patientAge"        INTEGER NOT NULL,
    "hvaAngle"          DOUBLE PRECISION,
    "imaAngle"          DOUBLE PRECISION,
    "dmaaAngle"         DOUBLE PRECISION,
    "painDuration"      TEXT,
    hypermobility       BOOLEAN NOT NULL DEFAULT FALSE,
    "jointCongruency"   TEXT NOT NULL DEFAULT 'congruent',
    osteoarthritis      TEXT NOT NULL DEFAULT 'none',
    "previousSurgery"   BOOLEAN NOT NULL DEFAULT FALSE,
    "previousSurgeryNote" TEXT,
    "clinicalNotes"     TEXT,
    severity            TEXT,
    "algorithmResult"   TEXT,
    "algorithmReason"   TEXT,
    "finalDecision"     TEXT,
    "overrideReason"    TEXT,
    "xrayImageUrl"      TEXT,
    "annotatedImageUrl" TEXT,
    "angleData"         TEXT,
    "doctorId"          TEXT NOT NULL REFERENCES "Doctor"(id),
    "alimtalkSent"      BOOLEAN NOT NULL DEFAULT FALSE,
    "alimtalkSentAt"    TIMESTAMP,
    "createdAt"         TIMESTAMP NOT NULL DEFAULT NOW(),
    "updatedAt"         TIMESTAMP NOT NULL DEFAULT NOW()
);
"""


def init_db() -> None:
    """데이터베이스 테이블 생성 (존재하지 않을 경우)."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(_CREATE_TABLES_SQL)
        conn.commit()
        logger.info("데이터베이스 테이블 초기화 완료")
    except Exception:
        conn.rollback()
        logger.exception("데이터베이스 초기화 실패")
        raise
    finally:
        _put_conn(conn)


# ---------------------------------------------------------------------------
# 인증
# ---------------------------------------------------------------------------

def authenticate(username: str, password: str) -> Optional[dict]:
    """사용자 인증. 성공 시 Doctor 딕셔너리 반환, 실패 시 None.

    Args:
        username: 로그인 사용자명
        password: 평문 비밀번호

    Returns:
        Doctor 정보 딕셔너리 또는 None
    """
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                'SELECT * FROM "Doctor" WHERE username = %s',
                (username,),
            )
            doctor = cur.fetchone()
        if doctor is None:
            return None
        stored_hash = doctor["passwordHash"]
        if bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8")):
            return dict(doctor)
        return None
    except Exception:
        logger.exception("인증 처리 중 오류 발생")
        return None
    finally:
        _put_conn(conn)


# ---------------------------------------------------------------------------
# Case CRUD
# ---------------------------------------------------------------------------

def create_case(data: dict) -> str:
    """새 케이스 생성.

    Args:
        data: 케이스 필드 딕셔너리 (id, reportHash 자동 생성)

    Returns:
        생성된 케이스 ID
    """
    case_id = data.get("id") or generate_cuid()
    report_hash = data.get("reportHash") or generate_cuid()
    now = datetime.utcnow()

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO "Case" (
                    id, "reportHash", "patientName", "patientBirth", "patientPhone",
                    "patientRegNo", "patientAge", "hvaAngle", "imaAngle", "dmaaAngle",
                    "painDuration", hypermobility, "jointCongruency", osteoarthritis,
                    "previousSurgery", "previousSurgeryNote", "clinicalNotes",
                    severity, "algorithmResult", "algorithmReason",
                    "finalDecision", "overrideReason",
                    "xrayImageUrl", "annotatedImageUrl", "angleData",
                    "doctorId", "alimtalkSent", "alimtalkSentAt",
                    "createdAt", "updatedAt"
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s
                )
                """,
                (
                    case_id,
                    report_hash,
                    data["patientName"],
                    data["patientBirth"],
                    data["patientPhone"],
                    data["patientRegNo"],
                    data["patientAge"],
                    data.get("hvaAngle"),
                    data.get("imaAngle"),
                    data.get("dmaaAngle"),
                    data.get("painDuration"),
                    data.get("hypermobility", False),
                    data.get("jointCongruency", "congruent"),
                    data.get("osteoarthritis", "none"),
                    data.get("previousSurgery", False),
                    data.get("previousSurgeryNote"),
                    data.get("clinicalNotes"),
                    data.get("severity"),
                    data.get("algorithmResult"),
                    data.get("algorithmReason"),
                    data.get("finalDecision"),
                    data.get("overrideReason"),
                    data.get("xrayImageUrl"),
                    data.get("annotatedImageUrl"),
                    data.get("angleData"),
                    data["doctorId"],
                    data.get("alimtalkSent", False),
                    data.get("alimtalkSentAt"),
                    now,
                    now,
                ),
            )
        conn.commit()
        logger.info("케이스 생성 완료: %s", case_id)
        return case_id
    except Exception:
        conn.rollback()
        logger.exception("케이스 생성 실패")
        raise
    finally:
        _put_conn(conn)


def update_case(case_id: str, data: dict) -> None:
    """기존 케이스 업데이트.

    Args:
        case_id: 업데이트할 케이스 ID
        data: 변경할 필드 딕셔너리
    """
    if not data:
        return

    # updatedAt 자동 갱신
    data["updatedAt"] = datetime.utcnow()

    # 허용된 컬럼만 필터링
    _allowed = {
        "patientName", "patientBirth", "patientPhone", "patientRegNo", "patientAge",
        "hvaAngle", "imaAngle", "dmaaAngle", "painDuration", "hypermobility",
        "jointCongruency", "osteoarthritis", "previousSurgery", "previousSurgeryNote",
        "clinicalNotes", "severity", "algorithmResult", "algorithmReason",
        "finalDecision", "overrideReason", "xrayImageUrl", "annotatedImageUrl",
        "angleData", "doctorId", "alimtalkSent", "alimtalkSentAt", "updatedAt",
    }
    filtered = {k: v for k, v in data.items() if k in _allowed}
    if not filtered:
        return

    set_clause = ", ".join(f'"{k}" = %s' for k in filtered)
    values = list(filtered.values()) + [case_id]

    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f'UPDATE "Case" SET {set_clause} WHERE id = %s',
                values,
            )
        conn.commit()
        logger.info("케이스 업데이트 완료: %s", case_id)
    except Exception:
        conn.rollback()
        logger.exception("케이스 업데이트 실패: %s", case_id)
        raise
    finally:
        _put_conn(conn)


def get_case(case_id: str) -> Optional[dict]:
    """ID로 케이스 조회.

    Args:
        case_id: 케이스 ID

    Returns:
        케이스 딕셔너리 또는 None
    """
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM "Case" WHERE id = %s', (case_id,))
            row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        logger.exception("케이스 조회 실패: %s", case_id)
        raise
    finally:
        _put_conn(conn)


def get_cases_by_doctor(doctor_id: str) -> list[dict]:
    """의사 ID로 케이스 목록 조회.

    Args:
        doctor_id: 의사 ID

    Returns:
        케이스 딕셔너리 리스트
    """
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                'SELECT * FROM "Case" WHERE "doctorId" = %s ORDER BY "createdAt" DESC',
                (doctor_id,),
            )
            rows = cur.fetchall()
        return [dict(r) for r in rows]
    except Exception:
        logger.exception("의사별 케이스 조회 실패: %s", doctor_id)
        raise
    finally:
        _put_conn(conn)


def get_all_cases() -> list[dict]:
    """전체 케이스 목록 조회.

    Returns:
        케이스 딕셔너리 리스트
    """
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM "Case" ORDER BY "createdAt" DESC')
            rows = cur.fetchall()
        return [dict(r) for r in rows]
    except Exception:
        logger.exception("전체 케이스 조회 실패")
        raise
    finally:
        _put_conn(conn)


def delete_case(case_id: str, doctor_id: str) -> bool:
    """케이스 삭제 (해당 의사만 가능).

    Args:
        case_id: 케이스 ID
        doctor_id: 요청 의사 ID

    Returns:
        삭제 성공 여부
    """
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                'DELETE FROM "Case" WHERE id = %s AND "doctorId" = %s',
                (case_id, doctor_id),
            )
            deleted = cur.rowcount > 0
        conn.commit()
        return deleted
    except Exception:
        conn.rollback()
        logger.exception("케이스 삭제 실패: %s", case_id)
        raise
    finally:
        _put_conn(conn)


def get_case_by_hash(report_hash: str) -> Optional[dict]:
    """리포트 해시로 케이스 조회.

    Args:
        report_hash: 고유 리포트 해시

    Returns:
        케이스 딕셔너리 또는 None
    """
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute('SELECT * FROM "Case" WHERE "reportHash" = %s', (report_hash,))
            row = cur.fetchone()
        return dict(row) if row else None
    except Exception:
        logger.exception("해시로 케이스 조회 실패: %s", report_hash)
        raise
    finally:
        _put_conn(conn)
