# -*- coding: utf-8 -*-
"""
카카오 알림톡 발송

측정기는 서버(Vultr)에 "이 케이스의 알림톡 발송"만 요청합니다.
서버가 작성자 본인 여부를 확인하고, 비즈톡 형식의 요청을 만들어
기존 중계 서버(203.245.41.19:5003)로 보냅니다.
발신키·템플릿 코드는 서버에만 있습니다 (server/hv_server/alimtalk.py).
"""

from __future__ import annotations

from desktop.core import api_client


def send_case_alimtalk(case_id: str) -> dict:
    """케이스의 환자에게 수술 안내서 알림톡을 보냅니다.

    Returns:
        성공: {"success": True, "message": str}
        실패: {"success": False, "error": str}
    """
    try:
        return {"success": True, "message": api_client.send_alimtalk(case_id)}
    except api_client.ApiError as e:
        return {"success": False, "error": e.message}
