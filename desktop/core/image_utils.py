# -*- coding: utf-8 -*-
"""
이미지 유틸리티 모듈
X-ray 이미지 업로드(Vercel Blob) 및 각도 측정 주석 이미지 생성
"""

import io
import logging
import math
from typing import Optional

import requests
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Vercel Blob 업로드 URL
VERCEL_BLOB_URL = "https://blob.vercel-storage.com"

# 업로드 타임아웃 (초)
UPLOAD_TIMEOUT = 60


def upload_to_vercel_blob(
    image_bytes: bytes,
    filename: str,
    blob_token: str,
) -> Optional[str]:
    """이미지를 Vercel Blob Storage에 업로드합니다.

    Args:
        image_bytes: 이미지 바이트 데이터
        filename: 저장할 파일명 (예: "xray_001.png")
        blob_token: Vercel Blob 읽기/쓰기 토큰

    Returns:
        업로드된 이미지의 URL, 실패 시 None
    """
    if not image_bytes:
        logger.error("업로드할 이미지 데이터가 비어있습니다")
        return None

    if not blob_token:
        logger.error("Vercel Blob 토큰이 설정되지 않았습니다")
        return None

    try:
        # Content-Type 추론
        content_type = "image/png"
        lower_name = filename.lower()
        if lower_name.endswith((".jpg", ".jpeg")):
            content_type = "image/jpeg"
        elif lower_name.endswith(".webp"):
            content_type = "image/webp"

        response = requests.put(
            f"{VERCEL_BLOB_URL}/{filename}",
            data=image_bytes,
            headers={
                "Authorization": f"Bearer {blob_token}",
                "x-api-version": "7",
                "Content-Type": content_type,
                "x-content-type": content_type,
            },
            timeout=UPLOAD_TIMEOUT,
        )

        response.raise_for_status()
        result = response.json()
        url = result.get("url")

        logger.info("이미지 업로드 성공: %s -> %s", filename, url)
        return url

    except requests.exceptions.Timeout:
        logger.error("이미지 업로드 타임아웃 (%d초 초과)", UPLOAD_TIMEOUT)
        return None
    except requests.exceptions.HTTPError as e:
        logger.error(
            "이미지 업로드 HTTP 오류: %s - %s",
            e.response.status_code,
            e.response.text,
        )
        return None
    except Exception:
        logger.exception("이미지 업로드 중 오류 발생")
        return None


def qimage_to_bytes(qimage, fmt: str = "PNG") -> bytes:
    """QImage 객체를 바이트 데이터로 변환합니다.

    Args:
        qimage: PyQt6 QImage 객체
        fmt: 이미지 형식 ('PNG', 'JPEG' 등)

    Returns:
        이미지 바이트 데이터
    """
    from PyQt6.QtCore import QBuffer, QIODevice

    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.ReadWrite)
    qimage.save(buffer, fmt)
    data = bytes(buffer.data())
    buffer.close()
    return data


def create_annotated_image(
    original_bytes: bytes,
    angle_data: list[dict],
) -> bytes:
    """원본 X-ray 이미지에 각도 측정 주석을 그립니다.

    Args:
        original_bytes: 원본 이미지 바이트 데이터
        angle_data: 각도 측정 데이터 리스트
            각 항목: {
                "type": str,        # 각도 유형 ("HVA", "IMA", "DMAA")
                "points": list,     # 측정 포인트 좌표 [(x1,y1), (x2,y2), ...]
                "angle": float,     # 측정 각도
                "color": str,       # 선 색상 (예: "#FF0000")
            }

    Returns:
        주석이 추가된 이미지 바이트 데이터 (PNG)
    """
    if not original_bytes:
        logger.error("주석 이미지 생성: 원본 이미지 데이터가 비어있습니다")
        return original_bytes

    try:
        image = Image.open(io.BytesIO(original_bytes)).convert("RGBA")
        overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # 폰트 설정 (시스템 기본 폰트 사용)
        try:
            font = ImageFont.truetype("malgun.ttf", size=max(16, image.width // 40))
        except (OSError, IOError):
            try:
                font = ImageFont.truetype("arial.ttf", size=max(16, image.width // 40))
            except (OSError, IOError):
                font = ImageFont.load_default()

        line_width = max(2, image.width // 300)

        for data in angle_data:
            angle_type = data.get("type", "")
            points = data.get("points", [])
            angle_value = data.get("angle", 0.0)
            color = data.get("color", "#FF0000")

            if len(points) < 2:
                continue

            # 측정선 그리기
            point_tuples = [tuple(p) if isinstance(p, (list, tuple)) else p for p in points]

            for i in range(len(point_tuples) - 1):
                draw.line(
                    [point_tuples[i], point_tuples[i + 1]],
                    fill=color,
                    width=line_width,
                )

            # 각 포인트에 원 표시
            dot_radius = max(3, line_width * 2)
            for pt in point_tuples:
                x, y = pt[0], pt[1]
                draw.ellipse(
                    [x - dot_radius, y - dot_radius, x + dot_radius, y + dot_radius],
                    fill=color,
                )

            # 각도 레이블 표시
            if len(point_tuples) >= 2:
                # 중간 지점 근처에 레이블
                mid_idx = len(point_tuples) // 2
                label_x = point_tuples[mid_idx][0] + 10
                label_y = point_tuples[mid_idx][1] - 20
                label = f"{angle_type}: {angle_value:.1f}°"

                # 텍스트 배경 (가독성 향상)
                bbox = draw.textbbox((label_x, label_y), label, font=font)
                padding = 4
                draw.rectangle(
                    [bbox[0] - padding, bbox[1] - padding, bbox[2] + padding, bbox[3] + padding],
                    fill=(0, 0, 0, 180),
                )
                draw.text((label_x, label_y), label, fill=color, font=font)

            # 각도 호 그리기 (포인트가 3개 이상인 경우)
            if len(point_tuples) >= 3:
                _draw_angle_arc(draw, point_tuples, color, line_width)

        # 오버레이 합성
        result = Image.alpha_composite(image, overlay)
        result = result.convert("RGB")

        output = io.BytesIO()
        result.save(output, format="PNG", quality=95)
        output.seek(0)

        logger.info("주석 이미지 생성 완료: %d개 각도 표시", len(angle_data))
        return output.read()

    except Exception:
        logger.exception("주석 이미지 생성 실패")
        return original_bytes


def _draw_angle_arc(
    draw: ImageDraw.ImageDraw,
    points: list[tuple],
    color: str,
    line_width: int,
) -> None:
    """세 점으로 정의된 각도의 호를 그립니다.

    Args:
        draw: ImageDraw 객체
        points: 최소 3개 포인트 [(x1,y1), (x2,y2), (x3,y3)]
                두 번째 점이 꼭짓점
        color: 선 색상
        line_width: 선 두께
    """
    if len(points) < 3:
        return

    # 꼭짓점(두 번째 점)에서 호 그리기
    vertex = points[1]
    p1 = points[0]
    p2 = points[2]

    # 각도 계산
    angle1 = math.atan2(p1[1] - vertex[1], p1[0] - vertex[0])
    angle2 = math.atan2(p2[1] - vertex[1], p2[0] - vertex[0])

    start_deg = math.degrees(angle1)
    end_deg = math.degrees(angle2)

    # 호 반지름
    radius = max(20, min(
        math.hypot(p1[0] - vertex[0], p1[1] - vertex[1]),
        math.hypot(p2[0] - vertex[0], p2[1] - vertex[1]),
    ) * 0.3)

    bbox = [
        vertex[0] - radius,
        vertex[1] - radius,
        vertex[0] + radius,
        vertex[1] + radius,
    ]

    draw.arc(bbox, start=start_deg, end=end_deg, fill=color, width=line_width)
