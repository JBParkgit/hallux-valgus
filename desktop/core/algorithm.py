# -*- coding: utf-8 -*-
"""
무지외반증 수술 결정 알고리즘
HVA, IMA, DMAA 각도 및 임상 소견을 기반으로 수술 방법을 추천합니다.
의사별 커스텀 설정을 지원합니다.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 수술 유형별 한국어 설명 (환자 리포트용)
# ---------------------------------------------------------------------------

# Akin 절골술이 이미 포함된 술식 — DMAA 기준으로 Akin 을 따로 붙이지 않는다
AKIN_INCLUDED_SURGERIES: frozenset[str] = frozenset({
    "핀홀 무지외반증 교정술",
    "핀홀교정술",  # 병원에서 함께 쓰는 짧은 이름
})

SURGERY_DESCRIPTIONS: dict[str, str] = {
    "핀홀 무지외반증 교정술": (
        "핀홀 무지외반증 교정술은 피부를 크게 절개하지 않고 작은 구멍을 통해 "
        "특수 기구로 뼈를 교정하는 최소침습 수술입니다. 제1중족골을 가로로 절골하여 "
        "각도를 바로잡고, 엄지발가락 첫마디뼈를 교정하는 Akin 절골술을 함께 시행합니다."
    ),
    "핀홀교정술": (
        "핀홀교정술(핀홀 무지외반증 교정술)은 피부를 크게 절개하지 않고 작은 구멍을 통해 "
        "특수 기구로 뼈를 교정하는 최소침습 수술입니다. 제1중족골을 가로로 절골하여 "
        "각도를 바로잡고, 엄지발가락 첫마디뼈를 교정하는 Akin 절골술을 함께 시행합니다."
    ),
    "Chevron 절골술": (
        "Chevron(쉐브론) 절골술은 경증 무지외반증에 가장 널리 사용되는 수술법입니다. "
        "제1중족골 원위부를 V자 형태로 절골하여 뼈를 이동시킨 후 고정하는 방법으로, "
        "수술 후 회복이 비교적 빠르고 예후가 좋습니다."
    ),
    "Scarf 절골술": (
        "Scarf(스카프) 절골술은 중등도 무지외반증에 적합한 수술법입니다. "
        "제1중족골 골간부를 Z자 형태로 절골하여 교정하는 방법으로, "
        "교정 범위가 넓고 안정적인 고정이 가능합니다."
    ),
    "근위 절골술": (
        "근위 절골술은 제1중족골의 기저부(몸쪽)를 절골하여 교정하는 수술입니다. "
        "중등도에서 중증 무지외반증에 사용되며, 큰 교정 효과를 기대할 수 있습니다."
    ),
    "Lapidus 절골술": (
        "Lapidus(라피더스) 절골술은 제1중족-내측 설상골 관절을 유합하는 수술입니다. "
        "중증 무지외반증이나 관절 과운동성이 있는 경우에 적합하며, "
        "재발률이 낮은 것이 장점입니다."
    ),
    "제1MTP 관절유합술": (
        "제1중족지절(MTP) 관절유합술은 엄지발가락 관절에 심한 관절염이 있는 경우 "
        "시행하는 수술입니다. 관절을 고정하여 통증을 제거하고 안정적인 보행을 "
        "가능하게 합니다."
    ),
    "Akin 절골술": (
        "Akin(에이킨) 절골술은 엄지발가락 기저부의 내측 쐐기 절골술로, "
        "원위 관절면 각도(DMAA)가 큰 경우 보조적으로 시행합니다. "
        "주 수술과 함께 진행하여 교정 효과를 높입니다."
    ),
}


def classify_severity(
    hva: float,
    ima: float,
    config: dict[str, Any] | None = None,
) -> str:
    """무지외반증 중증도 분류.

    Args:
        hva: 무지외반각 (Hallux Valgus Angle)
        ima: 제1-2중족골간각 (Intermetatarsal Angle)
        config: 의사별 알고리즘 설정 (None이면 기본값 사용)

    Returns:
        'mild', 'moderate', 'severe' 중 하나
    """
    if config:
        sev = config.get("severity", {})
    else:
        sev = {}

    severe_hva = sev.get("severe_hva", 40)
    severe_ima = sev.get("severe_ima", 16)
    moderate_hva = sev.get("moderate_hva", 30)
    moderate_ima = sev.get("moderate_ima", 14)

    if hva > severe_hva or ima > severe_ima:
        return "severe"
    if hva >= moderate_hva or ima >= moderate_ima:
        return "moderate"
    return "mild"


def recommend_surgery(
    hva: float,
    ima: float,
    dmaa: Optional[float] = None,
    age: Optional[int] = None,
    hypermobility: bool = False,
    joint_congruency: str = "congruent",
    osteoarthritis: str = "none",
    previous_surgery: bool = False,
    config: dict[str, Any] | None = None,
) -> dict:
    """무지외반증 수술 방법 추천 알고리즘.

    Args:
        hva: 무지외반각 (도)
        ima: 제1-2중족골간각 (도)
        dmaa: 원위 중족골 관절면 각도 (도, 선택)
        age: 환자 나이 (선택)
        hypermobility: 관절 과운동성 여부
        joint_congruency: 관절 적합성 ('congruent' 또는 'incongruent')
        osteoarthritis: 관절염 정도 ('none', 'mild', 'moderate', 'severe')
        previous_surgery: 이전 수술 이력 여부
        config: 의사별 알고리즘 설정 (None이면 기본값 사용)

    Returns:
        {
            'severity': str,
            'recommended_surgery': str,
            'additional_surgery': str | None,
            'reason': list[str],
            'description': str,
        }
    """
    severity = classify_severity(hva, ima, config)
    reason: list[str] = []
    recommended: str = ""
    additional: Optional[str] = None

    # Load surgery map from config
    if config:
        smap = config.get("surgery_map", {})
    else:
        smap = {}

    dmaa_threshold = config.get("dmaa_threshold", 10.0) if config else 10.0
    dmaa_surgery = config.get("dmaa_surgery", "Akin 절골술") if config else "Akin 절골술"
    age_warning = config.get("age_warning", 60) if config else 60

    reason.append(f"HVA: {hva:.1f}°, IMA: {ima:.1f}°")
    reason.append(f"중증도 분류: {severity}")

    # 1단계: 심한 골관절염 확인
    if osteoarthritis == "severe":
        recommended = smap.get("severe_oa", "제1MTP 관절유합술")
        reason.append("심한 골관절염으로 관절유합술 권장")

    # 2단계: 중증 + 관절 과운동성
    elif severity == "severe" and hypermobility:
        recommended = smap.get("severe_hypermobility", "Lapidus 절골술")
        reason.append("중증 무지외반증 + 관절 과운동성으로 수술 권장")

    # 3단계: 중증
    elif severity == "severe":
        recommended = smap.get("severe", "핀홀 무지외반증 교정술")
        reason.append("중증 무지외반증으로 수술 권장")

    # 4단계: 중등도
    elif severity == "moderate":
        recommended = smap.get("moderate", "핀홀 무지외반증 교정술")
        reason.append("중등도 무지외반증으로 수술 권장")

    # 5단계: 경증
    elif severity == "mild":
        recommended = smap.get("mild", "핀홀 무지외반증 교정술")
        reason.append("경증 무지외반증으로 수술 권장")

    # 보조 수술: DMAA 기준 초과 시 (주 수술에 이미 포함된 경우는 따로 붙이지 않음)
    if dmaa is not None and dmaa > dmaa_threshold:
        if _includes_surgery(recommended, dmaa_surgery):
            reason.append(f"DMAA {dmaa:.1f}° > {dmaa_threshold}° — {recommended}에 {dmaa_surgery}이 포함됨")
        else:
            additional = dmaa_surgery
            reason.append(f"DMAA {dmaa:.1f}° > {dmaa_threshold}°이므로 {dmaa_surgery} 추가 권장")

    # Custom rules
    if config:
        for rule in config.get("custom_rules", []):
            cond = rule.get("condition", "")
            msg = rule.get("message", "")
            if _eval_custom_rule(cond, hva=hva, ima=ima, dmaa=dmaa, age=age,
                                 hypermobility=hypermobility, severity=severity):
                reason.append(msg)
                if rule.get("override_surgery"):
                    recommended = rule["override_surgery"]
                if rule.get("override_additional"):
                    additional = rule["override_additional"]

    # 추가 참고 사항
    if previous_surgery:
        reason.append("이전 수술 이력 있음 - 재수술 시 주의 필요")

    if joint_congruency == "incongruent":
        reason.append("관절 부적합성 확인 - 수술 계획 시 고려 필요")

    if age is not None and age >= age_warning:
        reason.append(f"{age_warning}세 이상 고령 환자 - 회복 기간 고려 필요")

    # 설명 조합
    main_desc = ""
    for surgery_name, desc in SURGERY_DESCRIPTIONS.items():
        if surgery_name in recommended:
            main_desc = desc
            break

    if additional and additional in SURGERY_DESCRIPTIONS:
        main_desc += f"\n\n추가로, {SURGERY_DESCRIPTIONS[additional]}"

    result = {
        "severity": severity,
        "recommended_surgery": recommended,
        "additional_surgery": additional,
        "reason": reason,
        "description": main_desc,
    }

    logger.info(
        "수술 추천 완료: 중증도=%s, 추천=%s, 추가=%s",
        severity, recommended, additional,
    )

    return result


def _includes_surgery(main: str, extra: str) -> bool:
    """주 수술이 보조 수술을 이미 포함하는지 (예: 핀홀 교정술은 Akin 절골술 포함)."""
    if not main or not extra:
        return False
    if extra in main:  # 예: 'MICA (Chevron + Akin 절골술)'
        return True
    return extra == "Akin 절골술" and main in AKIN_INCLUDED_SURGERIES


def _eval_custom_rule(
    condition: str,
    *,
    hva: float,
    ima: float,
    dmaa: float | None,
    age: int | None,
    hypermobility: bool,
    severity: str,
) -> bool:
    """커스텀 룰 조건 평가 (간단한 표현식).

    지원 조건: 'hva>45', 'ima>18', 'age>70', 'severity==severe' 등
    """
    if not condition:
        return False
    try:
        # Safe evaluation with limited namespace
        ns = {
            "hva": hva, "ima": ima,
            "dmaa": dmaa if dmaa is not None else 0,
            "age": age if age is not None else 0,
            "hypermobility": hypermobility,
            "severity": severity,
        }
        return bool(eval(condition, {"__builtins__": {}}, ns))  # noqa: S307
    except Exception:
        return False
