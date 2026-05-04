# -*- coding: utf-8 -*-
"""
알림톡 발송 모듈
Biztalk 릴레이 서버를 통해 카카오 알림톡을 발송합니다.
"""

import logging
import uuid
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# 릴레이 서버 URL
RELAY_SERVER_URL = "http://203.245.41.19:5003/send-alimtalk"

# 요청 타임아웃 (초)
REQUEST_TIMEOUT = 30


def send_alimtalk(
    phone: str,
    template_code: str,
    message: str,
    buttons: Optional[list[dict]] = None,
) -> dict:
    """카카오 알림톡을 발송합니다.

    릴레이 서버(http://203.245.41.19:5003)를 통해 Biztalk API로 전달됩니다.
    릴레이 서버가 인증 토큰 관리를 내부적으로 처리합니다.

    Args:
        phone: 수신자 전화번호 (하이픈 포함/미포함 모두 가능, 내부에서 하이픈 제거)
        template_code: 알림톡 템플릿 코드
        message: 메시지 본문
        buttons: 버튼 리스트 (선택)
            예: [{"name": "수술 안내서 보기", "type": "WL",
                  "url_mobile": "https://...", "url_pc": "https://..."}]

    Returns:
        서버 응답 딕셔너리
        성공 시: {"success": True, "data": ...}
        실패 시: {"success": False, "error": str}
    """
    # 전화번호에서 하이픈 제거
    clean_phone = phone.replace("-", "").strip()

    if not clean_phone:
        logger.error("전화번호가 비어있습니다")
        return {"success": False, "error": "전화번호가 비어있습니다"}

    # 요청 본문 구성
    payload: dict = {
        "msgIdx": str(uuid.uuid4()),
        "channelId": "hospitalrun",
        "to": clean_phone,
        "templateCode": template_code,
        "message": message,
    }

    if buttons:
        payload["buttons"] = buttons

    try:
        logger.info(
            "알림톡 발송 요청: phone=%s, template=%s",
            clean_phone[-4:].rjust(len(clean_phone), "*"),  # 전화번호 마스킹
            template_code,
        )

        response = requests.post(
            RELAY_SERVER_URL,
            json=payload,
            timeout=REQUEST_TIMEOUT,
            headers={"Content-Type": "application/json"},
        )

        response.raise_for_status()
        result = response.json()

        logger.info("알림톡 발송 성공: msgIdx=%s", payload["msgIdx"])
        return {"success": True, "data": result}

    except requests.exceptions.Timeout:
        error_msg = f"알림톡 발송 타임아웃 ({REQUEST_TIMEOUT}초 초과)"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}

    except requests.exceptions.ConnectionError:
        error_msg = f"릴레이 서버 연결 실패: {RELAY_SERVER_URL}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}

    except requests.exceptions.HTTPError as e:
        error_msg = f"알림톡 발송 HTTP 오류: {e.response.status_code} - {e.response.text}"
        logger.error(error_msg)
        return {"success": False, "error": error_msg}

    except Exception as e:
        error_msg = f"알림톡 발송 중 예기치 않은 오류: {e}"
        logger.exception(error_msg)
        return {"success": False, "error": error_msg}


def build_report_button(report_url: str) -> list[dict]:
    """수술 안내서 보기 버튼을 생성합니다.

    Args:
        report_url: 리포트 URL

    Returns:
        알림톡 버튼 리스트
    """
    return [
        {
            "name": "수술 안내서 보기",
            "type": "WL",
            "url_mobile": report_url,
            "url_pc": report_url,
        }
    ]
