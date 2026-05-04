# -*- coding: utf-8 -*-
"""
의사별 수술 추천 알고리즘 설정 관리.
설정은 data/algorithm_config/{doctor_id}.json 에 저장됩니다.
"""

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "algorithm_config")


DEFAULT_SURGERIES = [
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
            "mild": "Chevron 절골술",
            "moderate": "Scarf 절골술",
            "severe": "근위 절골술",
            "severe_hypermobility": "Lapidus 절골술",
            "severe_oa": "제1MTP 관절유합술",
        },
        "dmaa_threshold": 10.0,
        "dmaa_surgery": "Akin 절골술",
        "age_warning": 60,
    }


def load_config(doctor_id: str) -> dict[str, Any]:
    """의사별 설정 로드. 없으면 기본값 반환."""
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    path = os.path.join(_CONFIG_DIR, f"{doctor_id}.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                saved = json.load(f)
            # Merge with defaults so new keys are always present
            cfg = default_config()
            _deep_merge(cfg, saved)
            return cfg
        except Exception:
            logger.exception("알고리즘 설정 로드 실패: %s", path)
    return default_config()


def save_config(doctor_id: str, config: dict[str, Any]) -> None:
    """의사별 설정 저장."""
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    path = os.path.join(_CONFIG_DIR, f"{doctor_id}.json")
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        logger.info("알고리즘 설정 저장: %s", path)
    except Exception:
        logger.exception("알고리즘 설정 저장 실패: %s", path)
        raise


def _deep_merge(base: dict, override: dict) -> None:
    """Recursively merge override into base (in-place)."""
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
