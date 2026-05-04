"""Canvas widget for X-ray angle measurement (HVA, IMA, DMAA).

Supports:
- Clipboard image paste (Ctrl+V)
- 4-point (2-line) angle measurement per type
- Live rubber-band line following mouse cursor
- Real-time angle preview while drawing second line
- Zoom (mouse wheel) and pan (middle mouse button)
- Color-coded measurement types with angle labels
- Dynamic measurement types (for bilateral L-/R- prefixed)
- Point dragging to adjust measurements
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPen,
    QPixmap,
    QWheelEvent,
)
from PyQt6.QtWidgets import QApplication, QWidget


@dataclass
class MeasurementData:
    """Stores points and computed angle for a single measurement type."""

    color: QColor
    points: list[QPointF] = field(default_factory=list)
    angle: float | None = None

    @property
    def is_complete(self) -> bool:
        return len(self.points) == 4

    def reset(self) -> None:
        self.points.clear()
        self.angle = None


def _is_dmaa(name: str) -> bool:
    """Check if measurement type is DMAA (including prefixed like L-DMAA)."""
    return name.endswith("DMAA")


class AngleCanvas(QWidget):
    """X-ray image canvas with interactive angle measurement.

    Signals:
        angle_measured(str, float): Emitted when a 4-point measurement is
            complete. Args are measurement type name and angle in degrees.
    """

    angle_measured = pyqtSignal(str, float)
    angle_reset = pyqtSignal(str)  # emitted when undo clears a completed measurement

    DEFAULT_TYPES: dict[str, QColor] = {
        "HVA": QColor("#e74c3c"),
        "IMA": QColor("#3498db"),
        "DMAA": QColor("#27ae60"),
    }

    # Keep TYPES as alias for backward compatibility
    TYPES = DEFAULT_TYPES

    _POINT_RADIUS = 4
    _LINE_WIDTH = 2.5
    _DRAG_HIT_RADIUS = 14

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(500, 400)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

        # Image
        self._pixmap: QPixmap | None = None
        self._zoom: float = 1.0
        self._pan_offset = QPointF(0, 0)
        self._is_panning = False
        self._pan_start = QPointF()
        self._drawing_line = False

        # Measurements (dynamic types)
        self._current_types: dict[str, QColor] = dict(self.DEFAULT_TYPES)
        self._measurements: dict[str, MeasurementData] = {
            name: MeasurementData(color=color)
            for name, color in self._current_types.items()
        }
        self._active_type: str = next(iter(self._current_types))

        # Live mouse position (image coords) for rubber-band
        self._mouse_img_pos: QPointF | None = None

        # Point dragging
        self._dragging: tuple[str, int] | None = None

        # Undo stack: tracks point placement order across all types
        self._action_stack: list[str] = []

    # ── Public API ──────────────────────────────────────────────

    @property
    def active_type(self) -> str:
        return self._active_type

    @active_type.setter
    def active_type(self, value: str) -> None:
        if value in self._measurements:
            self._active_type = value
            self.update()

    @property
    def current_types(self) -> dict[str, QColor]:
        return dict(self._current_types)

    def set_measurement_types(self, types: dict[str, QColor]) -> None:
        """Reconfigure measurement types (e.g. switch to bilateral L-/R-)."""
        self._current_types = dict(types)
        old = self._measurements
        self._measurements = {}
        for name, color in types.items():
            if name in old:
                self._measurements[name] = old[name]
                self._measurements[name].color = color
            else:
                self._measurements[name] = MeasurementData(color=color)
        if self._active_type not in self._measurements:
            self._active_type = next(iter(self._measurements))
        self.update()

    def set_image(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self._fit_image()
        self.update()

    def paste_from_clipboard(self) -> bool:
        clipboard = QApplication.clipboard()
        if clipboard is None:
            return False
        mime = clipboard.mimeData()
        if mime is None:
            return False
        if mime.hasImage():
            image = clipboard.image()
            if image and not image.isNull():
                self._pixmap = QPixmap.fromImage(image)
                self._fit_image()
                self.update()
                return True
        return False

    def get_angle(self, measurement_type: str) -> float | None:
        m = self._measurements.get(measurement_type)
        return m.angle if m else None

    def get_all_angles(self) -> dict[str, float | None]:
        """Return dict of all measurement angles."""
        return {name: m.angle for name, m in self._measurements.items()}

    def reset_measurement(self, measurement_type: str) -> None:
        m = self._measurements.get(measurement_type)
        if m:
            m.reset()
            self._action_stack = [n for n in self._action_stack if n != measurement_type]
            self.update()

    def reset_all(self) -> None:
        for m in self._measurements.values():
            m.reset()
        self._action_stack.clear()
        self._pixmap = None
        self._zoom = 1.0
        self._pan_offset = QPointF(0, 0)
        self.update()

    def undo_last_point(self) -> None:
        """Undo the last point placed (Ctrl+Z). Works across measurement types."""
        if not self._action_stack:
            return
        name = self._action_stack.pop()
        m = self._measurements.get(name)
        if m and m.points:
            was_complete = m.is_complete
            m.points.pop()
            if was_complete:
                m.angle = None
                self.angle_reset.emit(name)
            self.update()

    def get_measurements_data(self) -> dict:
        """Export measurement points/angles (without image) for DB storage."""
        result: dict = {}
        for name, m in self._measurements.items():
            result[name] = {
                "points": [(p.x(), p.y()) for p in m.points],
                "angle": m.angle,
            }
        return result

    def load_measurements_data(self, data: dict) -> None:
        """Restore measurement points/angles from saved data."""
        for name, m in self._measurements.items():
            if name in data:
                d = data[name]
                m.points = [QPointF(x, y) for x, y in d.get("points", [])]
                m.angle = d.get("angle")
            else:
                m.reset()
        self.update()

    def save_image_to_file(self, path: str) -> bool:
        """Save annotated X-ray image (with measurement lines & angles) to a file."""
        if not self._pixmap or self._pixmap.isNull():
            return False

        # Render measurements onto a copy of the original image
        result = QPixmap(self._pixmap.size())
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawPixmap(0, 0, self._pixmap)

        # Draw all completed measurements in image coordinates
        img_w = self._pixmap.width()
        line_width = max(2.0, img_w / 300)
        point_radius = max(4.0, img_w / 200)
        font_size = max(14, img_w // 40)

        for name, m in self._measurements.items():
            if not m.points:
                continue

            color = QColor(m.color)
            pen = QPen(color, line_width)
            painter.setPen(pen)

            pts = m.points

            # Draw points
            for p in pts:
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QBrush(color))
                painter.drawEllipse(p, point_radius, point_radius)

            # Draw line 1 (extended)
            if len(pts) >= 2:
                self._draw_extended_line_on_image(painter, pts[0], pts[1], pen, img_w)

            # Draw line 2 (extended)
            if len(pts) >= 4:
                self._draw_extended_line_on_image(painter, pts[2], pts[3], pen, img_w)

                # Draw angle label
                if m.angle is not None:
                    self._draw_angle_label_on_image(
                        painter, pts[3], name, m.angle, color, font_size,
                    )

        painter.end()
        return result.save(path, "PNG")

    @staticmethod
    def _draw_extended_line_on_image(
        painter: QPainter, p0: QPointF, p1: QPointF, pen: QPen, img_w: int,
    ) -> None:
        dx = p1.x() - p0.x()
        dy = p1.y() - p0.y()
        length = math.hypot(dx, dy)
        if length < 1:
            return
        nx, ny = dx / length, dy / length
        ext = img_w * 0.05
        painter.setPen(pen)
        painter.drawLine(
            QPointF(p0.x() - nx * ext, p0.y() - ny * ext),
            QPointF(p1.x() + nx * ext, p1.y() + ny * ext),
        )

    @staticmethod
    def _draw_angle_label_on_image(
        painter: QPainter,
        pos: QPointF,
        name: str,
        angle: float,
        color: QColor,
        font_size: int,
    ) -> None:
        text = f"{name}: {angle:.1f}\u00b0"
        font = QFont("\ub9d1\uc740 \uace0\ub515", font_size, QFont.Weight.Bold)
        painter.setFont(font)

        fm = painter.fontMetrics()
        text_rect = fm.boundingRect(text)
        padding = font_size // 2

        bg_rect = QRectF(
            pos.x() + font_size,
            pos.y() - text_rect.height() / 2 - padding,
            text_rect.width() + padding * 2,
            text_rect.height() + padding * 2,
        )

        bg_color = QColor(color)
        bg_color.setAlpha(200)
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(bg_rect, 6, 6)

        painter.setPen(QColor("white"))
        painter.drawText(bg_rect, Qt.AlignmentFlag.AlignCenter, text)

    def load_image_from_file(self, path: str) -> bool:
        """Load X-ray image from a file. Returns True on success."""
        import os
        if not os.path.exists(path):
            return False
        px = QPixmap(path)
        if px.isNull():
            return False
        self._pixmap = px
        self._fit_image()
        self.update()
        return True

    # ── Coordinate Transforms ───────────────────────────────────

    def _widget_to_image(self, pos: QPointF) -> QPointF:
        return QPointF(
            (pos.x() - self._pan_offset.x()) / self._zoom,
            (pos.y() - self._pan_offset.y()) / self._zoom,
        )

    def _image_to_widget(self, pos: QPointF) -> QPointF:
        return QPointF(
            pos.x() * self._zoom + self._pan_offset.x(),
            pos.y() * self._zoom + self._pan_offset.y(),
        )

    def _fit_image(self) -> None:
        if self._pixmap is None or self._pixmap.isNull():
            return
        w_ratio = self.width() / self._pixmap.width()
        h_ratio = self.height() / self._pixmap.height()
        self._zoom = min(w_ratio, h_ratio) * 0.95
        img_w = self._pixmap.width() * self._zoom
        img_h = self._pixmap.height() * self._zoom
        self._pan_offset = QPointF(
            (self.width() - img_w) / 2,
            (self.height() - img_h) / 2,
        )

    # ── Angle Calculation ───────────────────────────────────────

    @staticmethod
    def _calc_angle(p0: QPointF, p1: QPointF, p2: QPointF, p3: QPointF) -> float:
        """Calculate the acute angle between two lines in degrees (always <= 90)."""
        v1x = p1.x() - p0.x()
        v1y = p1.y() - p0.y()
        v2x = p3.x() - p2.x()
        v2y = p3.y() - p2.y()
        cross = v1x * v2y - v1y * v2x
        dot = v1x * v2x + v1y * v2y
        angle = math.degrees(abs(math.atan2(cross, dot)))
        if angle > 90:
            angle = 180 - angle
        return angle

    @staticmethod
    def _line_intersection(
        p0: QPointF, p1: QPointF, p2: QPointF, p3: QPointF,
    ) -> QPointF | None:
        d1x = p1.x() - p0.x()
        d1y = p1.y() - p0.y()
        d2x = p3.x() - p2.x()
        d2y = p3.y() - p2.y()
        denom = d1x * d2y - d1y * d2x
        if abs(denom) < 1e-10:
            return None
        t = ((p2.x() - p0.x()) * d2y - (p2.y() - p0.y()) * d2x) / denom
        return QPointF(p0.x() + t * d1x, p0.y() + t * d1y)

    # ── Hit Test & Recalc ────────────────────────────────────────

    def _hit_test_point(self, widget_pos: QPointF) -> tuple[str, int] | None:
        """Check if widget_pos is near any point of the active measurement type."""
        m = self._measurements.get(self._active_type)
        if m is None:
            return None
        for i, pt in enumerate(m.points):
            wpt = self._image_to_widget(pt)
            dx = widget_pos.x() - wpt.x()
            dy = widget_pos.y() - wpt.y()
            if math.hypot(dx, dy) <= self._DRAG_HIT_RADIUS:
                return (self._active_type, i)
        return None

    def _recalc_angle(self, name: str) -> None:
        """Recalculate angle for a complete measurement and emit signal."""
        m = self._measurements[name]
        if not m.is_complete:
            return
        pts = m.points
        raw = self._calc_angle(pts[0], pts[1], pts[2], pts[3])
        m.angle = (90 - raw) if _is_dmaa(name) else raw
        self.angle_measured.emit(name, m.angle)

    # ── Events ──────────────────────────────────────────────────

    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        """Suppress right-click context menu (right-click is used for panning)."""
        if event is not None:
            event.accept()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event is None:
            return
        if event.key() == Qt.Key.Key_V and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.paste_from_clipboard()
        elif event.key() == Qt.Key.Key_Z and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.undo_last_point()
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            return

        if event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton):
            self._is_panning = True
            self._pan_start = event.position() - self._pan_offset
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if event.button() == Qt.MouseButton.LeftButton and self._pixmap is not None:
            # Check for dragging existing point first
            hit = self._hit_test_point(event.position())
            if hit:
                self._dragging = hit
                self.setCursor(Qt.CursorShape.CrossCursor)
                return

            m = self._measurements[self._active_type]
            if m.is_complete:
                return

            # Place first point of a line pair; second point on release
            img_pos = self._widget_to_image(event.position())
            m.points.append(img_pos)
            self._action_stack.append(self._active_type)
            self._drawing_line = True
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            return
        if self._is_panning:
            self._pan_offset = event.position() - self._pan_start
            self.update()
            return

        # Dragging an existing point
        if self._dragging is not None:
            name, idx = self._dragging
            m = self._measurements[name]
            m.points[idx] = self._widget_to_image(event.position())
            if m.is_complete:
                self._recalc_angle(name)
            self.update()
            return

        # Track mouse for rubber-band line
        if self._pixmap is not None:
            self._mouse_img_pos = self._widget_to_image(event.position())
            m = self._measurements[self._active_type]
            n = len(m.points)
            if n in (1, 3):
                self.update()

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            return
        if event.button() == Qt.MouseButton.LeftButton and self._dragging is not None:
            self._dragging = None
            self.setCursor(Qt.CursorShape.ArrowCursor)
            return
        if event.button() == Qt.MouseButton.LeftButton and getattr(self, "_drawing_line", False):
            self._drawing_line = False
            m = self._measurements[self._active_type]
            n = len(m.points)
            # n is odd (1 or 3) means we just placed the start; place end point now
            if n in (1, 3) and self._mouse_img_pos is not None:
                m.points.append(self._mouse_img_pos)
                self._action_stack.append(self._active_type)
                if m.is_complete:
                    self._recalc_angle(self._active_type)
                self.update()
            return
        if event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton):
            self._is_panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def wheelEvent(self, event: QWheelEvent | None) -> None:
        if event is None:
            return
        if self._pixmap is None:
            return
        old_zoom = self._zoom
        delta = event.angleDelta().y()
        factor = 1.15 if delta > 0 else 1 / 1.15
        self._zoom = max(0.1, min(10.0, self._zoom * factor))
        mouse_pos = event.position()
        self._pan_offset = mouse_pos - (mouse_pos - self._pan_offset) * (self._zoom / old_zoom)
        self.update()

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        if self._pixmap is not None:
            self._fit_image()

    # ── Painting ────────────────────────────────────────────────

    def paintEvent(self, event) -> None:  # type: ignore[override]
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#1a1a2e"))

        if self._pixmap is None or self._pixmap.isNull():
            self._draw_placeholder(painter)
            painter.end()
            return

        # Draw image
        painter.save()
        painter.translate(self._pan_offset)
        painter.scale(self._zoom, self._zoom)
        painter.drawPixmap(0, 0, self._pixmap)
        painter.restore()

        # Draw all completed/in-progress measurements
        for name, m in self._measurements.items():
            is_active = name == self._active_type
            self._draw_measurement(painter, name, m, is_active)

        painter.end()

    def _draw_placeholder(self, painter: QPainter) -> None:
        painter.setPen(QColor("#7f8c8d"))
        painter.setFont(QFont("맑은 고딕", 14))
        painter.drawText(
            self.rect(),
            Qt.AlignmentFlag.AlignCenter,
            "Ctrl+V 로 X-ray 이미지를 붙여넣기 하세요",
        )

    def _draw_measurement(
        self, painter: QPainter, name: str, m: MeasurementData, is_active: bool,
    ) -> None:
        if not m.points and not is_active:
            return

        color = QColor(m.color)
        if not is_active:
            color.setAlpha(160)

        pen_solid = QPen(color, self._LINE_WIDTH)
        pen_dash = QPen(color, self._LINE_WIDTH, Qt.PenStyle.DashLine)

        n = len(m.points)
        widget_pts = [self._image_to_widget(p) for p in m.points]

        # Draw placed points
        for wp in widget_pts:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            painter.drawEllipse(wp, self._POINT_RADIUS, self._POINT_RADIUS)

        mouse_w = self._image_to_widget(self._mouse_img_pos) if self._mouse_img_pos else None

        # ── Line 1 ────────────────────────────────────────────
        if n == 1 and is_active and mouse_w:
            self._draw_extended_line(painter, widget_pts[0], mouse_w, pen_dash)
            ghost_color = QColor(color)
            ghost_color.setAlpha(100)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(ghost_color))
            painter.drawEllipse(mouse_w, self._POINT_RADIUS, self._POINT_RADIUS)

        elif n >= 2:
            self._draw_extended_line(painter, widget_pts[0], widget_pts[1], pen_solid)

        # ── Line 2 ────────────────────────────────────────────
        if n == 3 and is_active and mouse_w:
            self._draw_extended_line(painter, widget_pts[2], mouse_w, pen_dash)
            ghost_color = QColor(color)
            ghost_color.setAlpha(100)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(ghost_color))
            painter.drawEllipse(mouse_w, self._POINT_RADIUS, self._POINT_RADIUS)

            # Live angle preview at mouse position (end of second line)
            raw_live = self._calc_angle(
                m.points[0], m.points[1], m.points[2], self._mouse_img_pos,
            )
            live_angle = (90 - raw_live) if _is_dmaa(name) else raw_live
            self._draw_angle_label(painter, mouse_w, name, live_angle, color, preview=True)

        elif n >= 4:
            self._draw_extended_line(painter, widget_pts[2], widget_pts[3], pen_solid)

            if m.angle is not None:
                # Show label at the end of the second line (4th point)
                label_pos = widget_pts[3]
                self._draw_angle_label(painter, label_pos, name, m.angle, color, preview=False)

    def _draw_extended_line(
        self, painter: QPainter, p0: QPointF, p1: QPointF, pen: QPen,
    ) -> None:
        dx = p1.x() - p0.x()
        dy = p1.y() - p0.y()
        length = math.hypot(dx, dy)
        if length < 1:
            return
        nx, ny = dx / length, dy / length
        ext = 40
        painter.setPen(pen)
        painter.drawLine(
            QPointF(p0.x() - nx * ext, p0.y() - ny * ext),
            QPointF(p1.x() + nx * ext, p1.y() + ny * ext),
        )

    def _draw_angle_label(
        self,
        painter: QPainter,
        pos: QPointF,
        name: str,
        angle: float,
        color: QColor,
        preview: bool = False,
    ) -> None:
        text = f"{name}: {angle:.1f}°"
        font = QFont("맑은 고딕", 11, QFont.Weight.Bold)
        painter.setFont(font)

        fm = painter.fontMetrics()
        text_rect = fm.boundingRect(text)
        padding = 6

        bg_rect = QRectF(
            pos.x() + 12,
            pos.y() - text_rect.height() / 2 - padding,
            text_rect.width() + padding * 2,
            text_rect.height() + padding * 2,
        )

        bg_color = QColor(color)
        bg_color.setAlpha(140 if preview else 200)
        painter.setBrush(QBrush(bg_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(bg_rect, 4, 4)

        if preview:
            painter.setPen(QPen(QColor("white"), 1, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(bg_rect, 4, 4)

        painter.setPen(QColor("white"))
        painter.drawText(bg_rect, Qt.AlignmentFlag.AlignCenter, text)
