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
        view_changed(): zoom/pan or pan mode changed (for the zoom toolbar).
    """

    angle_measured = pyqtSignal(str, float)
    angle_reset = pyqtSignal(str)
    active_line_changed = pyqtSignal(str)
    lines_changed = pyqtSignal()
    image_changed = pyqtSignal()
    view_changed = pyqtSignal()

    ZOOM_MIN, ZOOM_MAX, ZOOM_STEP = 0.1, 10.0, 1.25

    _POINT_RADIUS = 4.5
    _LINE_WIDTH = 2.5
    _DRAG_HIT_RADIUS = 14

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setMinimumSize(500, 400)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setMouseTracking(True)
        self.setAcceptDrops(True)

        # Image / view
        self._pixmap: QPixmap | None = None
        self._zoom: float = 1.0
        self._pan_offset = QPointF(0, 0)
        self._is_panning = False
        self._pan_start = QPointF()
        self._fit_zoom = 1.0      # zoom that fits the whole image (= 100% on the toolbar)
        self._pan_mode = False    # '이동' 버튼: 왼쪽 드래그로 이미지 이동

        # Lines & angles
        self._prefixes: list[str] = [""]
        self._lines: dict[str, list[QPointF]] = {}  # line_id → [p0, p1]
        self._angles: dict[str, float | None] = {}
        # "" = 아무 선도 선택 안 됨 ('측정 시작'이나 선 버튼을 눌러야 선택됨)
        self._active_line: str = ""

        # Interaction state
        self._mouse_img_pos: QPointF | None = None
        self._draft_start: QPointF | None = None  # first point of a line being drawn
        self._dragging: tuple[str, int] | None = None  # (line_id, endpoint index)
        self._undo: list[tuple[str, list[QPointF] | None]] = []  # (line_id, previous)
        self._read_only = False
        # '측정 시작'을 누르거나 선을 그린 뒤에만 단계별 지시문을 보여 준다
        self._measure_started = False
        # Esc 로 측정을 중단한 직후 (지시문에 '중단했습니다' 표시)
        self._stopped = False

        self._reset_angle_table()

    # ── Configuration ───────────────────────────────────────────

    def set_sides(self, prefixes: list[str]) -> None:
        """Configure feet, e.g. ["L-", "R-"] for bilateral or [""] for one foot."""
        self._prefixes = list(prefixes) or [""]
        self._lines.clear()
        self._undo.clear()
        self._reset_angle_table()
        self.active_line = ""

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
        if line_id and line_id not in self.all_line_ids():
            return
        self._draft_start = None
        if line_id:
            self._stopped = False
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

    def start_measuring(self) -> None:
        """'측정 시작' 버튼: 하단 지시문을 단계 안내로 바꾼다."""
        self._measure_started = True
        self._stopped = False
        self.update()

    def stop_measuring(self) -> bool:
        """Esc: 측정 중단 — 긋던 선은 취소하고 선 선택을 해제한다 (그린 선은 유지).

        Returns True if there was a measurement in progress to stop.
        """
        if self._dragging is not None:
            return False  # 끝점을 끄는 중에는 무시
        was_measuring = bool(self._active_line) or self._draft_start is not None
        self._draft_start = None
        if was_measuring:
            self._stopped = True
            self.active_line = ""
        self.update()
        return was_measuring

    def reset_all(self) -> None:
        self._measure_started = False
        self._stopped = False
        self._lines.clear()
        self._undo.clear()
        self._draft_start = None
        self._dragging = None
        self._pixmap = None
        self._zoom = 1.0
        self._fit_zoom = 1.0
        self._pan_offset = QPointF(0, 0)
        self._pan_mode = False
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._recalc_angles()
        self.view_changed.emit()
        self.lines_changed.emit()
        self.active_line = ""
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
        """Paste an X-ray: image data (PACS/screenshot copy) or a copied image file."""
        clipboard = QApplication.clipboard()
        if clipboard is None or self._read_only:
            return False
        mime = clipboard.mimeData()
        if mime is None:
            return False
        if mime.hasImage():
            image = clipboard.image()
            if image and not image.isNull():
                self.set_image(QPixmap.fromImage(image))
                return True
        # 탐색기에서 이미지 파일을 Ctrl+C 한 경우
        return self._load_first_image_url(mime)

    def _load_first_image_url(self, mime) -> bool:
        if not mime.hasUrls():
            return False
        for url in mime.urls():
            if url.isLocalFile():
                px = QPixmap(url.toLocalFile())
                if not px.isNull():
                    self.set_image(px)
                    return True
        return False

    # Drag & drop an image file onto the canvas
    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        mime = event.mimeData()
        if not self._read_only and mime is not None and (mime.hasUrls() or mime.hasImage()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        mime = event.mimeData()
        ok = False
        if not self._read_only and mime is not None:
            if mime.hasImage():
                image = mime.imageData()
                if image is not None and not image.isNull():
                    self.set_image(QPixmap.fromImage(image))
                    ok = True
            if not ok:
                ok = self._load_first_image_url(mime)
        if ok:
            event.acceptProposedAction()
        else:
            event.ignore()

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
        self._measure_started = bool(self._lines)
        changed: list[str] = []
        for name, value in self._angles.items():
            saved = (data.get(name) or {}).get("angle")
            if value is not None and saved is not None and abs(value - saved) > 0.05:
                changed.append(name)
        self.lines_changed.emit()
        self.active_line = ""
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
        # 이 발의 선을 모두 그림 → 여기서 측정을 마친다.
        # 반대쪽 발로 자동으로 넘어가지 않는다 (한쪽만 측정하고 끝낼 수 있도록).
        self.active_line = ""

    def side_complete(self, prefix: str) -> bool:
        return all(self.has_line(prefix + k) for k in LINE_ORDER)

    def guide_lines(self) -> tuple[str, str]:
        """하단 중앙 지시문 (큰 글씨 본문, 작은 글씨 보조 설명)."""
        has_image = self._pixmap is not None and not self._pixmap.isNull()
        if self._read_only:
            return ("읽기 전용", "휠: 확대/축소   ·   가운데 버튼 드래그: 이동") if has_image else ("", "")
        if not self._measure_started and not self._lines:
            if not has_image:
                return "", ""  # 가운데 '붙여넣기' 안내가 대신한다
            return "‘측정 시작’ 버튼을 누르세요", "좌측 또는 우측 발 위의 버튼에서 시작합니다"
        if not has_image:
            return "먼저 X-ray 이미지를 붙여넣으세요", "Ctrl+V   ·   이미지 파일을 끌어다 놓아도 됩니다"
        if all(self.has_line(lid) for lid in self.all_line_ids()):
            scope = "양측 " if len(self._prefixes) > 1 else ""
            return f"{scope}측정 완료", "점을 드래그해 조정하거나, 선 버튼을 골라 다시 그릴 수 있습니다"
        if not self._active_line and self._stopped:
            return "측정을 중단했습니다", "그린 선은 그대로 남아 있습니다   ·   다시 하려면 ‘측정 시작’을 누르세요"
        if not self._active_line:
            names = {"L-": "좌측", "R-": "우측"}
            done = [p for p in self._prefixes if self.side_complete(p)]
            if len(done) == 1 and len(self._prefixes) > 1:
                other = next(p for p in self._prefixes if p != done[0])
                return (
                    f"{names.get(done[0], '')} 측정 완료",
                    f"{names.get(other, '')}도 측정하려면 ‘{names.get(other, '')} 측정 시작’을 누르세요"
                    "   ·   한쪽만 측정한다면 그대로 저장하면 됩니다",
                )
            return "‘측정 시작’ 버튼을 누르세요", "이어서 측정할 발의 버튼을 누르면 다음 선부터 그립니다"
        prefix, key = split_line_id(self._active_line)
        side = {"L-": "좌측 ", "R-": "우측 "}.get(prefix, "")
        step = LINE_ORDER.index(key) + 1
        label = LINE_LABELS[key]
        if self.has_line(self._active_line):
            return f"{side}{label} 다시 그리기", "드래그하면 이 선을 새로 그립니다   ·   Ctrl+Z 되돌리기   ·   Esc 중단"
        return (
            f"{step}/4   {side}{label}을 그리세요",
            "드래그로 선 긋기   ·   끝점을 끌어 조정   ·   Ctrl+Z 되돌리기   ·   Esc 측정 중단",
        )

    def guide_text(self) -> str:
        """Single-line form of the guide (kept for callers/tests)."""
        main, sub = self.guide_lines()
        return f"{main}  ·  {sub}" if main and sub else main

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
        self._fit_zoom = self._zoom
        img_w = self._pixmap.width() * self._zoom
        img_h = self._pixmap.height() * self._zoom
        self._pan_offset = QPointF((self.width() - img_w) / 2, (self.height() - img_h) / 2)
        self.view_changed.emit()

    # ── View controls (zoom toolbar) ────────────────────────────

    def _zoom_at(self, factor: float, anchor: QPointF) -> None:
        if self._pixmap is None or self._pixmap.isNull():
            return
        old_zoom = self._zoom
        self._zoom = max(self.ZOOM_MIN, min(self.ZOOM_MAX, self._zoom * factor))
        self._pan_offset = anchor - (anchor - self._pan_offset) * (self._zoom / old_zoom)
        self.update()
        self.view_changed.emit()

    def zoom_in(self) -> None:
        self._zoom_at(self.ZOOM_STEP, QPointF(self.width() / 2, self.height() / 2))

    def zoom_out(self) -> None:
        self._zoom_at(1 / self.ZOOM_STEP, QPointF(self.width() / 2, self.height() / 2))

    def fit_view(self) -> None:
        self._fit_image()
        self.update()

    def zoom_percent(self) -> int:
        """Zoom relative to 'fit whole image' (fit = 100%)."""
        return round(self._zoom / self._fit_zoom * 100) if self._fit_zoom else 100

    @property
    def pan_mode(self) -> bool:
        return self._pan_mode

    def set_pan_mode(self, on: bool) -> None:
        if on == self._pan_mode:
            return
        self._pan_mode = on
        self._draft_start = None
        self.setCursor(Qt.CursorShape.OpenHandCursor if on else Qt.CursorShape.CrossCursor)
        self.update()
        self.view_changed.emit()

    def _hit_test(self, widget_pos: QPointF) -> tuple[str, int] | None:
        """Nearest endpoint of an existing line within the hit radius.

        While the active line is still undrawn, clicks always start a new line
        (its start often sits right on another line's endpoint, e.g. the MTP
        joint), so no endpoint is grabbed then.
        """
        if self._active_line and not self.has_line(self._active_line):
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
        # Ctrl+V 는 화면(CaseWorkflowWidget)의 단축키가 처리한다 (실패 시 안내 포함)
        if event.key() == Qt.Key.Key_Z and ctrl:
            self.undo_last()
        # Esc(측정 중단)도 화면의 단축키가 처리한다
        else:
            super().keyPressEvent(event)

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        if event is None:
            return
        pan_button = event.button() in (Qt.MouseButton.MiddleButton, Qt.MouseButton.RightButton) or (
            self._pan_mode and event.button() == Qt.MouseButton.LeftButton
        )
        if pan_button:
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

        if not self._active_line:
            return  # 선이 선택되지 않음 → '측정 시작'을 눌러야 그린다 (하단 지시문 참고)
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

        if self._pan_mode:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif self._read_only:
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
        if self._is_panning:
            self._is_panning = False
            self.setCursor(Qt.CursorShape.OpenHandCursor if self._pan_mode else Qt.CursorShape.CrossCursor)
            self.view_changed.emit()
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
        self._measure_started = True
        self._after_lines_changed()
        self._advance_from(line_id)

    def wheelEvent(self, event: QWheelEvent | None) -> None:
        if event is None or self._pixmap is None:
            return
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self._zoom_at(factor, event.position())

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
            self._draw_guide(painter)  # '측정 시작' 후 이미지가 없으면 붙여넣기 안내
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
        """하단 중앙의 큰 지시문 (본문 + 보조 설명 두 줄)."""
        main, sub = self.guide_lines()
        if not main:
            return
        main_font = theme.font(15, QFont.Weight.Bold)
        sub_font = theme.font(10, QFont.Weight.DemiBold)
        max_text_w = max(120, self.width() - 120)
        painter.setFont(main_font)
        fm_main = painter.fontMetrics()
        main = fm_main.elidedText(main, Qt.TextElideMode.ElideRight, max_text_w)
        painter.setFont(sub_font)
        fm_sub = painter.fontMetrics()
        sub = fm_sub.elidedText(sub, Qt.TextElideMode.ElideRight, max_text_w) if sub else ""

        dot = 14
        pad_x = 28
        text_w = max(fm_main.horizontalAdvance(main), fm_sub.horizontalAdvance(sub) if sub else 0)
        w = text_w + pad_x * 2 + dot + 14
        h = fm_main.height() + (fm_sub.height() + 6 if sub else 0) + 26
        r = QRectF((self.width() - w) / 2, self.height() - h - 22, w, h)

        painter.setPen(QPen(QColor(255, 255, 255, 60), 1.5))
        painter.setBrush(QColor(10, 14, 23, 230))
        painter.drawRoundedRect(r, 16, 16)

        if self._read_only or not self._measure_started or not self._active_line:
            dot_color = QColor(theme.MUTED) if self._read_only else QColor(theme.PRIMARY)
        else:
            dot_color = line_color(self._active_line)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(dot_color)
        text_left = r.left() + pad_x + dot + 14
        main_rect = QRectF(text_left, r.top() + 13, text_w, fm_main.height())
        painter.drawEllipse(QPointF(r.left() + pad_x + dot / 2, main_rect.center().y()), dot / 2, dot / 2)

        painter.setFont(main_font)
        painter.setPen(QColor(255, 255, 255, 245))
        painter.drawText(main_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, main)
        if sub:
            painter.setFont(sub_font)
            painter.setPen(QColor(255, 255, 255, 165))
            sub_rect = QRectF(text_left, main_rect.bottom() + 6, text_w, fm_sub.height())
            painter.drawText(sub_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, sub)

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
