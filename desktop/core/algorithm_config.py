# -*- coding: utf-8 -*-
"""
의사별 수술 추천 알고리즘 설정 관리.
설정은 서버에 저장되고, 이 PC의 data/algorithm_config/{doctor_id}.json 에 사본이 남습니다.
"""

import json
import logging
import os
from typing import Any

from desktop.core.paths import data_dir

logger = logging.getLogger(__name__)

_CONFIG_DIR = data_dir("algorithm_config")


DEFAULT_SURGERIES = [
    "핀홀 무지외반증 교정술",  # 최소침습: 가로 절골(transverse) + Akin 절골술 — 병원 주력 술식
    "Chevron 절골술",
    "Scarf 절골술",
    "근위 절골술",
    "Lapidus 절골술",
    "제1MTP 관절유합술",
    "Akin 절골술",
]


def default_config() -> dict[str, Any]:
    """기본 알고리즘 설정값 반환."""
    return {
        "surgeries": list(DEFAULT_SURGERIES),
        "severity": {
            "moderate_hva": 30,
            "moderate_ima": 14,
            "severe_hva": 40,
            "severe_ima": 16,
        },
        "surgery_map": {
            "mild": "핀홀 무지외반증 교정술",
            "moderate": "핀홀 무지외반증 교정술",
            "severe": "핀홀 무지외반증 교정술",
            "severe_hypermobility": "Lapidus 절골술",
            "severe_oa": "제1MTP 관절유합술",
        },
        "dmaa_threshold": 10.0,
        "dmaa_surgery": "Akin 절골술",
        "age_warning": 60,
    }


def _local_path(doctor_id: str) -> str:
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    return os.path.join(_CONFIG_DIR, f"{doctor_id}.json")


def load_config(doctor_id: str) -> dict[str, Any]:
    """의사별 설정 로드: 서버 → (실패 시) 이 PC의 사본 → 기본값.

    서버에 저장하므로 어느 PC에서 로그인해도 같은 설정을 씁니다.
    """
    saved: dict | None = None
    try:
        from desktop.core import api_client
        if api_client.current_doctor():
            saved = api_client.get_algorithm_config()
    except Exception:
        logger.warning("서버에서 알고리즘 설정을 불러오지 못해 이 PC의 사본을 사용합니다.")
        saved = None

    path = _local_path(doctor_id)
    if saved is None and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                saved = json.load(f)
        except Exception:
            logger.exception("알고리즘 설정 로드 실패: %s", path)

    cfg = default_config()
    if saved:
        # Merge with defaults so new keys are always present
        _deep_merge(cfg, saved)
    return cfg


def save_config(doctor_id: str, config: dict[str, Any]) -> None:
    """의사별 설정 저장: 서버에 저장하고 이 PC에도 사본을 남깁니다."""
    from desktop.core import api_client
    api_client.put_algorithm_config(config)  # 실패하면 ApiError → 화면에 표시
    path = _local_path(doctor_id)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception:
        logger.exception("알고리즘 설정 사본 저장 실패: %s", path)


def _deep_merge(base: dict, override: dict) -> None:
    """Recursively merge override into base (in-place)."""
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
