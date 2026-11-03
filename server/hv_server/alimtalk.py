"""Kakao Alimtalk via the existing relay server (203.245.41.19:5003).

The relay forwards the JSON body to Biztalk's sendAlimTalk unchanged, so the
payload must already be in Biztalk format — the same format the image-capture
client (multi_client.py) uses successfully.

The message text must match the approved Kakao template *exactly*
(only the #{변수} parts may differ).
"""

from __future__ import annotations

import time

import requests

from hv_server import config

REQUEST_TIMEOUT = 15


def build_message(patient_name: str) -> str:
    """Body text of the hallux report template (must equal the approved template)."""
    return (
        f"[달려라병원] {patient_name}님의 무지외반증 수술 안내서가 준비되었습니다.\n\n"
        f"아래 '수술 안내서 보기' 버튼을 눌러 확인해 주세요.\n\n"
        f"달려라병원 (문의:1600-7511)"
    )


def build_payload(phone: str, patient_name: str, report_url: str) -> dict:
    clean_phone = "".join(ch for ch in phone if ch.isdigit())
    return {
        "recipient": clean_phone,
        "msgIdx": f"hv-{int(time.time() * 1000)}-{clean_phone[-4:]}",
        "countryCode": "82",
        "senderKey": config.ALIMTALK_SENDER_KEY,
        "tmpltCode": config.ALIMTALK_TEMPLATE_CODE,
        "message": build_message(patient_name),
        "resMethod": "PUSH",
        "pfId": config.ALIMTALK_PF_ID,
        "attach": {
            "button": [
                {
                    "name": "수술 안내서 보기",
                    "type": "WL",
                    "url_mobile": report_url,
                    "url_pc": report_url,
                }
            ]
        },
    }


def send(phone: str, patient_name: str, report_url: str) -> tuple[bool, str]:
    """Returns (success, message)."""
    if not config.ALIMTALK_SENDER_KEY or not config.ALIMTALK_TEMPLATE_CODE:
        return False, "서버에 알림톡 발신키/템플릿 코드가 설정되지 않았습니다."
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) < 10:
        return False, "환자 전화번호가 올바르지 않습니다."

    headers = {"Content-Type": "application/json"}
    if config.ALIMTALK_RELAY_SECRET:
        headers["X-Relay-Secret"] = config.ALIMTALK_RELAY_SECRET
    try:
        res = requests.post(
            config.RELAY_URL,
            json=build_payload(phone, patient_name, report_url),
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        return False, f"알림톡 중계 서버 연결 실패: {exc.__class__.__name__}"

    try:
        body = res.json()
    except ValueError:
        body = {}
    if res.ok and body.get("status") == "success":
        return True, "발송 완료"
    return False, str(body.get("message") or f"중계 서버 오류 (HTTP {res.status_code})")
