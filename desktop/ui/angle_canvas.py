"""Canvas widget for X-ray angle measurement, organised around *lines*.

Each foot (side prefix "L-" / "R-") has four lines, drawn in this order:

    M1   제1중족골 축            (shared reference axis)
    P1   제1근위지골 축          → HVA  = angle(M1, P1)
    M2   제2중족골 축            → IMA  = angle(M1, M2)
    ART  제1중족골 원위 관절면 선 → DMAA = 90° − angle(M1, ART)

The canvas only draws the lines; angle values are shown outside the image
(side panels) via the ``angle_measured`` / ``angle_reset`` signals.

Interaction:
- Drag on the image to draw the active line; the next undrawn line on the
  same side becomes active automatically.
- Choose any line (``active_line``) to draw — or redraw — it on demand.
- Drag an endpoint of an existing line to adjust it.
- Ctrl+Z undoes the last line change, Ctrl+V pastes an X-ray image.
- Wheel zooms, middle/right-button drag pans.

Saved data keeps the original per-angle 4-point format
(``{"L-HVA": {"points": [M1a, M1b, P1a, P1b], "angle": ...}, ...}``) so older
cases and the web report keep working.
"""

from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QMouseEvent,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QWheelEvent,
)
from PyQt6.QtWidgets import QApplication, QWidget

from desktop.ui import theme

# Line keys in drawing order
LINE_ORDER: tuple[str, ...] = ("M1", "P1", "M2", "ART")

LINE_LABELS: dict[str, str] = {
    "M1": "제1중족골 축",
    "P1": "제1근위지골 축",
    "M2": "제2중족골 축",
    "ART": "원위 관절면 선",
}

# angle base name → second line (first line is always M1)
ANGLE_LINES: dict[str, str] = {"HVA": "P1", "IMA": "M2", "DMAA": "ART"}
_LINE_TO_ANGLE: dict[str, str] = {v: k for k, v in ANGLE_LINES.items()}

_MIN_DRAG_PX = 4  # shorter drags are treated as clicks (no line)


def split_line_id(line_id: str) -> tuple[str, str]:
    """'L-P1' → ('L-', 'P1')."""
    if line_id[:2] in ("L-", "R-"):
        return line_id[:2], line_id[2:]
    return "", line_id


def line_color(line_id: str) -> QColor:
    prefix, key = split_line_id(line_id)
    if key == "M1":
        return QColor(theme.ANGLE_COLORS["AXIS"])
    return QColor(theme.ANGLE_COLORS[prefix + _LINE_TO_ANGLE[key]])


def _acute_angle(p0: QPointF, p1: QPointF, p2: QPointF, p3: QPointF) -> float:
    """Acute angle between two lines in degrees (0–90)."""
    v1x, v1y = p1.x() - p0.x(), p1.y() - p0.y()
    v2x, v2y = p3.x() - p2.x(), p3.y() - p2.y()
    angle = math.degrees(abs(math.atan2(v1x * v2y - v1y * v2x, v1x * v2x + v1y * v2y)))
    return 180 - angle if angle > 90 else angle


class AngleCanvas(QWidget):
    """X-ray image canvas with line-based angle measurement.

    Signals:
        angle_measured(str, float): an angle (e.g. "L-HVA") was (re)computed.
        angle_reset(str): an angle became unavailable (a needed line removed).
        active_line_changed(str): the line to draw next changed (e.g. "L-P1").
        lines_changed(): any line was added, moved, or removed.
    """

    angle_measured = pyqtSignal(str, float)
    angle_reset = pyqtSignal(str)
    active_line_changed = pyqtSignal(str)
    lines_changed = pyqtSignal()
    image_changed = pyqtSignal()

    _POINT_RADIUS = 4.5
    _LINE_WIDTH = 2.5
    _DRAG_HIT_RADIUS = 14

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(500, 400)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)

        # Image / view
        self._pixmap: QPixmap | None = None
        self._zoom: float = 1.0
        self._pan_offset = QPointF(0, 0)
        self._is_panning = False
        self._pan_start = QPointF()

        # Lines & angles
        self._prefixes: list[str] = [""]
        self._lines: dict[str, list[QPointF]] = {}  # line_id → [p0, p1]
        self._angles: dict[str, float | None] = {}
        self._active_line: str = "M1"

        # Interaction state
        self._mouse_img_pos: QPointF | None = None
        self._draft_start: QPointF | None = None  # first point of a line being drawn
        self._dragging: tuple[str, int] | None = None  # (line_id, endpoint index)
        self._undo: list[tuple[str, list[QPointF] | None]] = []  # (line_id, previous)
        self._read_only = False

        self._reset_angle_table()

    # ── Configuration ───────────────────────────────────────────

    def set_sides(self, prefixes: list[str]) -> None:
        """Configure feet, e.g. ["L-", "R-"] for bilateral or [""] for one foot."""
        self._prefixes = list(prefixes) or [""]
        self._lines.clear()
        self._undo.clear()
        self._reset_angle_table()
        self.active_line = self._prefixes[0] + "M1"

    def _reset_angle_table(self) -> None:
        self._angles = {p + a: None for p in self._prefixes for a in ANGLE_LINES}

    def all_line_ids(self) -> list[str]:
        return [p + k for p in self._prefixes for k in LINE_ORDER]

    # ── Public API ──────────────────────────────────────────────

    @property
    def active_line(self) -> str:
        return self._active_line

    @active_line.setter
    def active_line(self, line_id: str) -> None:
        if line_id not in self.all_line_ids():
            return
        self._draft_start = None
        if line_id != self._active_line:
            self._active_line = line_id
            self.active_line_changed.emit(line_id)
        self.update()

    @property
    def read_only(self) -> bool:
        return self._read_only

    def set_read_only(self, value: bool) -> None:
        """View-only mode (another doctor's case): zoom/pan only, no edits."""
        self._read_only = value
        self._draft_start = None
        self._dragging = None
        self.update()

    @property
    def is_adjusting(self) -> bool:
        """True while the user is dragging an existing endpoint."""
        return self._dragging is not None

    def has_line(self, line_id: str) -> bool:
        return len(self._lines.get(line_id, [])) == 2

    def get_angle(self, measurement_type: str) -> float | None:
        return self._angles.get(measurement_type)

    def get_all_angles(self) -> dict[str, float | None]:
        return dict(self._angles)

    def clear_line(self, line_id: str) -> None:
        if self._read_only:
            return
        if line_id in self._lines:
            self._undo.append((line_id, [QPointF(p) for p in self._lines[line_id]]))
            del self._lines[line_id]
            self._after_lines_changed()
            self.active_line = line_id

    def reset_all(self) -> None:
        self._lines.clear()
        self._undo.clear()
        self._draft_start = None
        self._dragging = None
        self._pixmap = None
        self._zoom = 1.0
        self._pan_offset = QPointF(0, 0)
        self._recalc_angles()
        self.lines_changed.emit()
        self.active_line = self._prefixes[0] + "M1"
        self.update()

    def undo_last(self) -> None:
        """Undo the last line change (Ctrl+Z)."""
        if not self._undo or self._read_only:
            return
        line_id, previous = self._undo.pop()
        if previous is None:
            self._lines.pop(line_id, None)
        else:
            self._lines[line_id] = previous
        self._after_lines_changed()
        self.active_line = line_id

    # Backward-compatible alias
    undo_last_point = undo_last

    def set_image(self, pixmap: QPixmap, *, notify: bool = True) -> None:
        self._pixmap = pixmap
        self._fit_image()
        self.update()
        if notify:
            self.image_changed.emit()

    def has_image(self) -> bool:
        return self._pixmap is not None and not self._pixmap.isNull()

    def raw_image_png(self) -> bytes | None:
        """Original X-ray as PNG bytes (no annotations), for upload."""
        if not self.has_image():
            return None
        from PyQt6.QtCore import QBuffer, QByteArray, QIODevice
        data = QByteArray()
        buf = QBuffer(data)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        self._pixmap.save(buf, "PNG")
        buf.close()
        return bytes(data)

    def load_image_bytes(self, data: bytes) -> bool:
        px = QPixmap()
        if not px.loadFromData(data):
            return False
        self.set_image(px, notify=False)
        return True

    def paste_from_clipboard(self) -> bool:
        clipboard = QApplication.clipboard()
        if clipboard is None:
            return False
        mime = clipboard.mimeData()
        if self._read_only or mime is None or not mime.hasImage():
            return False
        image = clipboard.image()
        if image and not image.isNull():
            self.set_image(QPixmap.fromImage(image))
            return True
        return False

    def load_image_from_file(self, path: str) -> bool:
        import os
        if not os.path.exists(path):
            return False
        px = QPixmap(path)
        if px.isNull():
            return False
        self.set_image(px, notify=False)
        return True

    def save_raw_image(self, path: str) -> bool:
        """Save the original X-ray (no annotations)."""
        if not self._pixmap or self._pixmap.isNull():
            return False
        return self._pixmap.save(path, "PNG")

    def save_image_to_file(self, path: str) -> bool:
        """Save the X-ray with measurement lines drawn on it (no angle labels)."""
        if not self._pixmap or self._pixmap.isNull():
            return False
        result = QPixmap(self._pixmap.size())
        painter = QPainter(result)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.drawPixmap(0, 0, self._pixmap)
        img_w = self._pixmap.width()
        width = max(2.0, img_w / 300)
        radius = max(4.0, img_w / 200)
        ext = img_w * 0.05
        for line_id, pts in self._lines.items():
            if len(pts) != 2:
                continue
            color = line_color(line_id)
            self._draw_extended(painter, pts[0], pts[1], QPen(color, width), ext)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(color))
            for p in pts:
                painter.drawEllipse(p, radius, radius)
        painter.end()
        return result.save(path, "PNG")

    # ── Persistence (per-angle 4-point format) ──────────────────

    def get_measurements_data(self) -> dict:
        result: dict = {}
        for prefix in self._prefixes:
            m1 = self._lines.get(prefix + "M1", [])
            for angle, second in ANGLE_LINES.items():
                sec = self._lines.get(prefix + second, [])
                pts = (m1 if len(m1) == 2 else []) + (sec if len(m1) == 2 else [])
                result[prefix + angle] = {
                    "points": [(p.x(), p.y()) for p in pts],
                    "angle": self._angles.get(prefix + angle),
                }
        # Every drawn line, even ones without an M1 axis yet (not an angle
        # entry: the web report skips keys without "points").
        result["lines"] = {
            lid: [(p.x(), p.y()) for p in pts]
            for lid, pts in self._lines.items()
            if len(pts) == 2
        }
        return result

    def load_measurements_data(self, data: dict) -> list[str]:
        """Restore lines from saved data.

        Returns angle names whose recomputed value differs from the saved value
        (happens for cases saved before the M1 axis was shared).
        """
        self._lines.clear()
        self._undo.clear()
        saved_lines = data.get("lines")
        if isinstance(saved_lines, dict):
            valid = set(self.all_line_ids())
            for lid, pts in saved_lines.items():
                if lid in valid and len(pts) == 2:
                    self._lines[lid] = [QPointF(*pts[0]), QPointF(*pts[1])]
        for prefix in ([] if isinstance(saved_lines, dict) else self._prefixes):
            # M1 axis: first angle that has it (HVA preferred)
            for angle in ANGLE_LINES:
                pts = (data.get(prefix + angle) or {}).get("points") or []
                if len(pts) >= 2:
                    self._lines[prefix + "M1"] = [QPointF(*pts[0]), QPointF(*pts[1])]
                    break
            for angle, second in ANGLE_LINES.items():
                pts = (data.get(prefix + angle) or {}).get("points") or []
                if len(pts) >= 4:
                    self._lines[prefix + second] = [QPointF(*pts[2]), QPointF(*pts[3])]

        self._recalc_angles(emit=False)
        changed: list[str] = []
        for name, value in self._angles.items():
            saved = (data.get(name) or {}).get("angle")
            if value is not None and saved is not None and abs(value - saved) > 0.05:
                changed.append(name)
        self.lines_changed.emit()
        self._advance_from(self._prefixes[0] + "M1", include_self=True)
        self.update()
        return changed

    # ── Internals: lines → angles ───────────────────────────────

    def _recalc_angles(self, emit: bool = True) -> None:
        for prefix in self._prefixes:
            m1 = self._lines.get(prefix + "M1")
            for angle, second in ANGLE_LINES.items():
                name = prefix + angle
                sec = self._lines.get(prefix + second)
                old = self._angles.get(name)
                if m1 and sec and len(m1) == 2 and len(sec) == 2:
                    raw = _acute_angle(m1[0], m1[1], sec[0], sec[1])
                    new: float | None = (90 - raw) if angle == "DMAA" else raw
                else:
                    new = None
                self._angles[name] = new
                if not emit:
                    continue
                if new is None and old is not None:
                    self.angle_reset.emit(name)
                elif new is not None and (old is None or abs(new - old) > 1e-9):
                    self.angle_measured.emit(name, new)

    def _after_lines_changed(self) -> None:
        self._recalc_angles()
        self.lines_changed.emit()
        self.update()

    def _advance_from(self, line_id: str, include_self: bool = False) -> None:
        """Make the next undrawn line on the same side active (in LINE_ORDER)."""
        prefix, key = split_line_id(line_id)
        start = LINE_ORDER.index(key)
        order = LINE_ORDER[start:] + LINE_ORDER[:start]
        if not include_self:
            order = order[1:]
        for k in order:
            if not self.has_line(prefix + k):
                self.active_line = prefix + k
                return
        # This side is done → continue on the next side (e.g. left → right)
        idx = self._prefixes.index(prefix)
        for other in self._prefixes[idx + 1:] + self._prefixes[:idx]:
            for k in LINE_ORDER:
                if not self.has_line(other + k):
                    self.active_line = other + k
                    return
        if include_self:
            self.active_line = line_id

    def guide_text(self) -> str:
        if self._pixmap is None:
            return ""
        if self._read_only:
            return "읽기 전용  ·  휠: 확대/축소   가운데 버튼 드래그: 이동"
        prefix, key = split_line_id(self._active_line)
        side = {"L-": "좌측 ", "R-": "우측 "}.get(prefix, "")
        step = LINE_ORDER.index(key) + 1
        label = LINE_LABELS[key]
        if all(self.has_line(lid) for lid in self.all_line_ids()):
            scope = "양측 " if len(self._prefixes) > 1 else ""
            return f"{scope}측정 완료  ·  점을 드래그해 조정하거나 선을 골라 다시 그릴 수 있습니다"
        if self.has_line(self._active_line):
            return f"{side}{label}을 다시 그리려면 드래그하세요"
        return f"{step}/4  {side}{label}을 드래그로 그리세요"

    # ── Coordinate transforms ───────────────────────────────────

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
        self._pan_offset = QPointF((self.width() - img_w) / 2, (self.height() - img_h) / 2)

    def _hit_test(self, widget_pos: QPointF) -> tuple[str, int] | None:
        """Nearest endpoint of an existing line within the hit radius.

        While the active line is still undrawn, clicks always start a new line
        (its start often sits right on another line's endpoint, e.g. the MTP
        joint), so no endpoint is grabbed then.
        """
        if not self.has_line(self._active_line):
            return None
        best: tuple[float, tuple[str, int]] | None = None
        for line_id, pts in self._lines.items():
            for i, p in enumerate(pts):
                wp = self._image_to_widget(p)
                d = math.hypot(widget_pos.x() - wp.x(), widget_pos.y() - wp.y())
                if d <= self._DRAG_HIT_RADIUS and (best is None or d < best[0]):
                    best = (d, (line_id, i))
        return best[1] if best else None

    # ── Events ──────────────────────────────────────────────────

    def contextMenuEvent(self, event) -> None:  # type: ignore[override]
        if event is not None:
            event.accept()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event is None:
            return
        ctrl = event.modifiers() & Qt.KeyboardModifier.ControlModifier
        if event.key() == Qt.Key.Key_V and ctrl:
            self.paste_from_clipboard()
        elif event.key() == Qt.Key.Key_Z and ctrl:
            self.undo_last()
        elif event.key() == Qt.Key.Key_Escape and self._draft_start is not None:
            self._draft_start = None
            self.update()
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
        if event.button() != Qt.MouseButton.LeftButton or self._pixmap is None or self._read_only:
            return

        hit = self._hit_test(event.position())
        if hit:
            line_id, _ = hit
            self._undo.append((line_id, [QPointF(p) for p in self._lines[line_id]]))
            self._dragging = hit
            self.setCursor(Qt.CursorShape.SizeAllCursor)
            return

        self._draft_start = self._widget_to_image(event.position())
        self._mouse_img_pos = self._draft_start
        self.update()

    def mouseMoveEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            return
        if self._is_panning:
            self._pan_offset = event.position() - self._pan_start
            self.update()
            return
        if self._pixmap is None:
            return
        self._mouse_img_pos = self._widget_to_image(event.position())

        if self._dragging is not None:
            line_id, idx = self._dragging
            self._lines[line_id][idx] = self._mouse_img_pos
            self._recalc_angles()
            self.update()
            return

        if self._read_only:
            self.setCursor(Qt.CursorShape.ArrowCursor)
        elif self._draft_start is not None:
            self.update()
        elif self._hit_test(event.position()):
            self.setCursor(Qt.CursorShape.SizeAllCursor)
        else:
            self.setCursor(Qt.CursorShape.CrossCursor)

    def mouseReleaseEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            return
        if event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton):
            self._is_panning = False
            self.setCursor(Qt.CursorShape.CrossCursor)
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self._dragging is not None:
            line_id, _ = self._dragging
            self._dragging = None
            # Drop the undo snapshot if the endpoint didn't actually move
            if self._undo and self._undo[-1][0] == line_id and self._undo[-1][1] == self._lines.get(line_id):
                self._undo.pop()
            self.setCursor(Qt.CursorShape.CrossCursor)
            self.lines_changed.emit()
            self.update()
            return

        if self._draft_start is None:
            return
        start = self._draft_start
        end = self._widget_to_image(event.position())
        self._draft_start = None
        ws, we = self._image_to_widget(start), self._image_to_widget(end)
        if math.hypot(we.x() - ws.x(), we.y() - ws.y()) < _MIN_DRAG_PX:
            self.update()
            return

        line_id = self._active_line
        previous = self._lines.get(line_id)
        self._undo.append((line_id, [QPointF(p) for p in previous] if previous else None))
        self._lines[line_id] = [start, end]
        self._after_lines_changed()
        self._advance_from(line_id)

    def wheelEvent(self, event: QWheelEvent | None) -> None:
        if event is None or self._pixmap is None:
            return
        old_zoom = self._zoom
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
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
        painter.fillRect(self.rect(), QColor(theme.BG))
        frame = QPainterPath()
        frame.addRoundedRect(QRectF(self.rect()), 14, 14)
        painter.setClipPath(frame)
        painter.fillRect(self.rect(), QColor(theme.CANVAS_BG))

        if self._pixmap is None or self._pixmap.isNull():
            self._draw_placeholder(painter)
            painter.end()
            return

        painter.save()
        painter.translate(self._pan_offset)
        painter.scale(self._zoom, self._zoom)
        painter.drawPixmap(0, 0, self._pixmap)
        painter.restore()

        # Inactive lines first, active line on top
        ids = sorted(self._lines, key=lambda lid: lid == self._active_line)
        for line_id in ids:
            pts = self._lines[line_id]
            if len(pts) == 2:
                self._draw_line(painter, line_id, pts, line_id == self._active_line)

        # Line being drawn
        if self._draft_start is not None and self._mouse_img_pos is not None:
            color = line_color(self._active_line)
            a = self._image_to_widget(self._draft_start)
            b = self._image_to_widget(self._mouse_img_pos)
            self._draw_extended(painter, a, b, QPen(color, self._LINE_WIDTH + 0.5, Qt.PenStyle.DashLine), 40)
            for p in (a, b):
                painter.setPen(QPen(QColor(255, 255, 255, 220), 1.5))
                painter.setBrush(QBrush(color))
                painter.drawEllipse(p, self._POINT_RADIUS, self._POINT_RADIUS)

        self._draw_guide(painter)
        painter.end()

    def _draw_line(self, painter: QPainter, line_id: str, pts: list[QPointF], active: bool) -> None:
        color = line_color(line_id)
        if not active:
            color.setAlpha(185)
        if self._draft_start is not None and active:
            color.setAlpha(70)  # being redrawn: fade the old version
        width = self._LINE_WIDTH + (0.8 if active else 0)
        a, b = (self._image_to_widget(p) for p in pts)
        self._draw_extended(painter, a, b, QPen(color, width), 40)
        for p in (a, b):
            painter.setPen(QPen(QColor(255, 255, 255, 220 if active else 130), 1.5))
            painter.setBrush(QBrush(color))
            painter.drawEllipse(p, self._POINT_RADIUS, self._POINT_RADIUS)

    @staticmethod
    def _draw_extended(painter: QPainter, p0: QPointF, p1: QPointF, pen: QPen, ext: float) -> None:
        dx, dy = p1.x() - p0.x(), p1.y() - p0.y()
        length = math.hypot(dx, dy)
        if length < 1:
            return
        nx, ny = dx / length, dy / length
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawLine(
            QPointF(p0.x() - nx * ext, p0.y() - ny * ext),
            QPointF(p1.x() + nx * ext, p1.y() + ny * ext),
        )

    def _draw_guide(self, painter: QPainter) -> None:
        text = self.guide_text()
        if not text:
            return
        painter.setFont(theme.font(10, QFont.Weight.DemiBold))
        fm = painter.fontMetrics()
        dot = 10
        w = fm.horizontalAdvance(text) + 40 + dot
        h = 34
        r = QRectF((self.width() - w) / 2, self.height() - h - 16, w, h)
        painter.setPen(QPen(QColor(255, 255, 255, 40), 1))
        painter.setBrush(QColor(10, 14, 23, 215))
        painter.drawRoundedRect(r, h / 2, h / 2)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(theme.MUTED) if self._read_only else line_color(self._active_line))
        painter.drawEllipse(QPointF(r.left() + 18, r.center().y()), dot / 2, dot / 2)
        painter.setPen(QColor(255, 255, 255, 235))
        painter.drawText(r.adjusted(18 + dot, 0, 0, 0), Qt.AlignmentFlag.AlignCenter, text)

    def _draw_placeholder(self, painter: QPainter) -> None:
        c = QRectF(self.rect()).center()
        box = QRectF(c.x() - 190, c.y() - 110, 380, 220)

        pen = QPen(QColor(255, 255, 255, 40), 1.5, Qt.PenStyle.DashLine)
        pen.setDashPattern([6, 5])
        painter.setPen(pen)
        painter.setBrush(QColor(255, 255, 255, 6))
        painter.drawRoundedRect(box, 16, 16)

        g = QRectF(c.x() - 22, box.top() + 34, 44, 36)
        gpen = QPen(QColor(255, 255, 255, 110), 2)
        gpen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(gpen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(g, 6, 6)
        mount = QPainterPath()
        mount.moveTo(g.left() + 6, g.bottom() - 6)
        mount.lineTo(g.left() + 18, g.top() + 16)
        mount.lineTo(g.left() + 27, g.bottom() - 12)
        mount.lineTo(g.left() + 32, g.bottom() - 17)
        mount.lineTo(g.right() - 6, g.bottom() - 6)
        painter.drawPath(mount)
        painter.drawEllipse(QPointF(g.right() - 11, g.top() + 10), 3, 3)

        painter.setPen(QColor(255, 255, 255, 220))
        painter.setFont(theme.font(13, QFont.Weight.DemiBold))
        painter.drawText(
            QRectF(box.left(), g.bottom() + 16, box.width(), 24),
            Qt.AlignmentFlag.AlignCenter,
            "X-ray 이미지를 붙여넣으세요",
        )

        painter.setFont(theme.font(9, QFont.Weight.DemiBold))
        fm = painter.fontMetrics()
        y = g.bottom() + 52
        items = ["Ctrl", "+", "V"]
        widths = [fm.horizontalAdvance(t) + (18 if t != "+" else 4) for t in items]
        x = c.x() - (sum(widths) + 8 * (len(items) - 1)) / 2
        for t, w in zip(items, widths):
            r = QRectF(x, y, w, 24)
            if t != "+":
                painter.setPen(QPen(QColor(255, 255, 255, 60), 1))
                painter.setBrush(QColor(255, 255, 255, 18))
                painter.drawRoundedRect(r, 6, 6)
                painter.setPen(QColor(255, 255, 255, 200))
            else:
                painter.setPen(QColor(255, 255, 255, 110))
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, t)
            x += w + 8

        painter.setPen(QColor(255, 255, 255, 90))
        painter.setFont(theme.font(9))
        painter.drawText(
            QRectF(box.left(), y + 34, box.width(), 20),
            Qt.AlignmentFlag.AlignCenter,
            "휠: 확대/축소   ·   가운데 버튼 드래그: 이동",
        )
