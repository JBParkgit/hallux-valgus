# -*- coding: utf-8 -*-
"""
환자 정보 파서
DreamSoft SMS_Patient.txt 파일에서 환자 데이터를 로드하고 검색합니다.
"""

import logging
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

# 기본 환자 파일 경로
DEFAULT_PATIENT_FILE = r"C:\DreamSoft\SMS_Patient.txt"


def load_patients(filepath: str = DEFAULT_PATIENT_FILE) -> list[dict]:
    """환자 파일에서 전체 환자 목록을 로드합니다.

    파일 형식: 생년월일,전화,이름,등록번호,질병코드 (cp949 인코딩)

    Args:
        filepath: SMS_Patient.txt 파일 경로

    Returns:
        환자 딕셔너리 리스트
        각 항목: {birth, phone, name, reg_no, disease_code}
    """
    patients: list[dict] = []

    try:
        with open(filepath, "r", encoding="cp949") as f:
            for line_no, line in enumerate(f, start=1):
                line = line.strip()
                if not line:
                    continue

                parts = line.split(",")
                if len(parts) < 5:
                    logger.warning(
                        "파싱 오류 (라인 %d): 필드 부족 - '%s'", line_no, line
                    )
                    continue

                birth_raw = parts[0].strip()
                try:
                    age = calculate_age(birth_raw)
                except ValueError:
                    age = 0

                patient = {
                    "birth": birth_raw,
                    "birth_date": birth_raw,
                    "phone": parts[1].strip(),
                    "name": parts[2].strip(),
                    "reg_no": parts[3].strip(),
                    "disease_code": parts[4].strip(),
                    "age": age,
                }
                patients.append(patient)

        logger.info("환자 데이터 로드 완료: %d명", len(patients))

    except FileNotFoundError:
        logger.error("환자 파일을 찾을 수 없습니다: %s", filepath)
    except UnicodeDecodeError:
        logger.error("파일 인코딩 오류 (cp949 예상): %s", filepath)
    except Exception:
        logger.exception("환자 파일 로드 중 오류 발생: %s", filepath)

    return patients


def search_patients(
    query: str, patients: Optional[list[dict]] = None
) -> list[dict]:
    """이름 또는 등록번호로 환자를 검색합니다.

    Args:
        query: 검색어 (이름 또는 등록번호 부분 일치)
        patients: 검색 대상 환자 목록 (None이면 파일에서 로드)

    Returns:
        검색 결과 환자 딕셔너리 리스트
    """
    if patients is None:
        patients = load_patients()

    if not query or not query.strip():
        return patients

    query = query.strip()
    results = [
        p
        for p in patients
        if query in p.get("name", "") or query in p.get("reg_no", "")
    ]

    logger.info("환자 검색 '%s': %d건 검색됨", query, len(results))
    return results


def calculate_age(birth_str: str) -> int:
    """생년월일 문자열로부터 나이를 계산합니다.

    Args:
        birth_str: YYMMDD 형식의 생년월일 문자열
                  연도 규칙: 00~24 -> 2000년대, 25~99 -> 1900년대

    Returns:
        현재 나이 (만 나이)

    Raises:
        ValueError: 올바르지 않은 생년월일 형식
    """
    if not birth_str or len(birth_str) < 6:
        raise ValueError(f"올바르지 않은 생년월일 형식: '{birth_str}'")

    try:
        year_2digit = int(birth_str[:2])
        month = int(birth_str[2:4])
        day = int(birth_str[4:6])
    except ValueError:
        raise ValueError(f"생년월일을 숫자로 변환할 수 없습니다: '{birth_str}'")

    # 2자리 연도 -> 4자리 연도 변환
    # 현재 연도 기준으로 경계값 설정 (현재 2026년 기준: 00~26 -> 2000대)
    current_year_2digit = datetime.now().year % 100
    if year_2digit <= current_year_2digit:
        year = 2000 + year_2digit
    else:
        year = 1900 + year_2digit

    try:
        birth_date = datetime(year, month, day)
    except ValueError:
        raise ValueError(f"유효하지 않은 날짜: {year}년 {month}월 {day}일")

    today = datetime.now()
    age = today.year - birth_date.year

    # 생일이 아직 지나지 않았으면 1살 차감
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1

    return age
