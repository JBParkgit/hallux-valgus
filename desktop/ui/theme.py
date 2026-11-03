"""Central design system: palette, typography, global stylesheet, and vector icons.

모든 화면이 같은 색/폰트/간격 규칙을 쓰도록 여기서 한 번에 정의한다.
"""

from __future__ import annotations

from PyQt6.QtCore import QPointF, QRectF, QSize, Qt
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QIcon,
    QPainter,
    QPainterPath,
    QPalette,
    QPen,
    QPixmap,
)
from PyQt6.QtWidgets import QApplication, QFrame, QGraphicsDropShadowEffect, QLabel, QWidget

# ── Palette ──────────────────────────────────────────────────────────

BG = "#F3F5F9"
SURFACE = "#FFFFFF"
SURFACE_ALT = "#F8FAFC"
BORDER = "#E3E8EF"
BORDER_STRONG = "#CDD5E0"

TEXT = "#0F172A"
TEXT_2 = "#475569"
MUTED = "#94A3B8"

PRIMARY = "#2F5BEA"
PRIMARY_HOVER = "#2449C9"
PRIMARY_PRESSED = "#1D3BA6"
PRIMARY_SOFT = "#EDF2FF"

SUCCESS = "#0E9F6E"
SUCCESS_SOFT = "#E6F6EF"
WARNING = "#D97706"
WARNING_SOFT = "#FDF3E3"
DANGER = "#E5484D"
DANGER_HOVER = "#CC3439"
DANGER_SOFT = "#FDECEC"

SIDEBAR = "#0E1526"
SIDEBAR_HOVER = "#18223A"
SIDEBAR_TEXT = "#C3CBDA"
SIDEBAR_MUTED = "#6B7894"

CANVAS_BG = "#0A0E17"

# 각도 측정 색 (좌/우 구분)
ANGLE_COLORS: dict[str, str] = {
    "HVA": "#F2555A",
    "IMA": "#4C8DFF",
    "DMAA": "#22C38E",
    "L-HVA": "#F2555A",
    "L-IMA": "#4C8DFF",
    "L-DMAA": "#22C38E",
    "R-HVA": "#FF6FAE",
    "R-IMA": "#8B7CFF",
    "R-DMAA": "#2CC4D6",
    # 세 각도가 공유하는 제1중족골 축
    "AXIS": "#FACC15",
}

SEVERITY_STYLE: dict[str, tuple[str, str]] = {
    # 한국어 중증도 → (글자색, 배경색)
    "경증": (SUCCESS, SUCCESS_SOFT),
    "중등도": (WARNING, WARNING_SOFT),
    "중증": (DANGER, DANGER_SOFT),
}

# ── Typography ───────────────────────────────────────────────────────

_FAMILY: str | None = None


def family() -> str:
    """Preferred UI font family (Pretendard → Noto Sans KR → 맑은 고딕)."""
    global _FAMILY
    if _FAMILY is None:
        available = set(QFontDatabase.families())
        for name in ("Pretendard", "Pretendard Variable", "Noto Sans KR", "맑은 고딕", "Malgun Gothic"):
            if name in available:
                _FAMILY = name
                break
        else:
            _FAMILY = "Sans Serif"
    return _FAMILY


def font(size: float = 10, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    f = QFont(family())
    f.setPointSizeF(size)
    f.setWeight(weight)
    f.setStyleHint(QFont.StyleHint.SansSerif)
    f.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
    return f


# ── Helpers ──────────────────────────────────────────────────────────


def card(parent: QWidget | None = None, shadow: bool = True) -> QFrame:
    """White rounded surface with a soft shadow."""
    frame = QFrame(parent)
    frame.setObjectName("card")
    if shadow:
        add_shadow(frame)
    return frame


def add_shadow(widget: QWidget, blur: int = 24, y: int = 4, alpha: int = 18) -> None:
    eff = QGraphicsDropShadowEffect(widget)
    eff.setBlurRadius(blur)
    eff.setOffset(0, y)
    eff.setColor(QColor(15, 23, 42, alpha))
    widget.setGraphicsEffect(eff)


def label(text: str, role: str = "", parent: QWidget | None = None) -> QLabel:
    """QLabel with a semantic role (title, subtitle, caption, section, value...)."""
    lbl = QLabel(text, parent)
    if role:
        lbl.setProperty("role", role)
    return lbl


def set_variant(widget: QWidget, variant: str) -> None:
    widget.setProperty("variant", variant)
    repolish(widget)


def repolish(widget: QWidget) -> None:
    st = widget.style()
    if st is not None:
        st.unpolish(widget)
        st.polish(widget)
    widget.update()


def pill_style(fg: str, bg: str) -> str:
    return (
        f"color: {fg}; background-color: {bg}; border-radius: 10px; "
        f"padding: 3px 10px; font-weight: 600;"
    )


def severity_pill_style(sev_kr: str) -> str:
    fg, bg = SEVERITY_STYLE.get(sev_kr, (MUTED, SURFACE_ALT))
    return pill_style(fg, bg)


# ── Vector icons ─────────────────────────────────────────────────────


def icon(name: str, color: str = TEXT_2, size: int = 18) -> QIcon:
    """Small line icons drawn with QPainter (no image assets needed)."""
    scale = 3
    px = QPixmap(size * scale, size * scale)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size * scale / 24.0, size * scale / 24.0)
    pen = QPen(QColor(color), 1.9)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)

    if name == "dashboard":
        for x, y, w, h in ((3, 3, 8, 10), (13, 3, 8, 6), (13, 11, 8, 10), (3, 15, 8, 6)):
            p.drawRoundedRect(QRectF(x, y, w, h), 2, 2)
    elif name == "plus":
        p.drawLine(QPointF(12, 5), QPointF(12, 19))
        p.drawLine(QPointF(5, 12), QPointF(19, 12))
    elif name == "settings":
        for y, kx in ((6, 15), (12, 8), (18, 13)):
            p.drawLine(QPointF(4, y), QPointF(20, y))
            p.setBrush(QColor(SIDEBAR if color == SIDEBAR_TEXT else SURFACE))
            p.drawEllipse(QPointF(kx, y), 2.4, 2.4)
            p.setBrush(Qt.BrushStyle.NoBrush)
    elif name == "logout":
        path = QPainterPath()
        path.moveTo(10, 4)
        path.lineTo(5, 4)
        path.quadTo(4, 4, 4, 5)
        path.lineTo(4, 19)
        path.quadTo(4, 20, 5, 20)
        path.lineTo(10, 20)
        p.drawPath(path)
        p.drawLine(QPointF(10, 12), QPointF(20, 12))
        p.drawLine(QPointF(16, 8), QPointF(20, 12))
        p.drawLine(QPointF(16, 16), QPointF(20, 12))
    elif name == "search":
        p.drawEllipse(QPointF(10.5, 10.5), 6, 6)
        p.drawLine(QPointF(15, 15), QPointF(20, 20))
    elif name == "folder":
        path = QPainterPath()
        path.moveTo(3, 7)
        path.quadTo(3, 5, 5, 5)
        path.lineTo(9, 5)
        path.lineTo(11, 7)
        path.lineTo(19, 7)
        path.quadTo(21, 7, 21, 9)
        path.lineTo(21, 17)
        path.quadTo(21, 19, 19, 19)
        path.lineTo(5, 19)
        path.quadTo(3, 19, 3, 17)
        path.closeSubpath()
        p.drawPath(path)
    elif name == "user":
        p.drawEllipse(QPointF(12, 8), 4, 4)
        path = QPainterPath()
        path.moveTo(4, 20)
        path.quadTo(12, 10, 20, 20)
        p.drawPath(path)
    elif name == "save":
        p.drawRoundedRect(QRectF(4, 4, 16, 16), 2, 2)
        p.drawRect(QRectF(8, 4, 8, 5))
        p.drawRect(QRectF(7.5, 13, 9, 7))
    elif name == "send":
        path = QPainterPath()
        path.moveTo(3, 11)
        path.lineTo(21, 3)
        path.lineTo(14, 21)
        path.lineTo(11, 13)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(QPointF(11, 13), QPointF(21, 3))
    elif name == "copy":
        p.drawRoundedRect(QRectF(8, 8, 12, 12), 2, 2)
        path = QPainterPath()
        path.moveTo(16, 8)
        path.lineTo(16, 5)
        path.quadTo(16, 4, 15, 4)
        path.lineTo(5, 4)
        path.quadTo(4, 4, 4, 5)
        path.lineTo(4, 15)
        path.quadTo(4, 16, 5, 16)
        path.lineTo(8, 16)
        p.drawPath(path)
    elif name == "refresh":
        p.drawArc(QRectF(4, 4, 16, 16), 30 * 16, 280 * 16)
        p.drawLine(QPointF(19, 3.5), QPointF(19, 8.5))
        p.drawLine(QPointF(19, 8.5), QPointF(14, 8.5))
    elif name == "sparkle":
        path = QPainterPath()
        path.moveTo(12, 3)
        path.quadTo(13, 11, 21, 12)
        path.quadTo(13, 13, 12, 21)
        path.quadTo(11, 13, 3, 12)
        path.quadTo(11, 11, 12, 3)
        p.drawPath(path)
    elif name == "shield":
        path = QPainterPath()
        path.moveTo(12, 3)
        path.lineTo(20, 6)
        path.lineTo(20, 12)
        path.quadTo(20, 18, 12, 21)
        path.quadTo(4, 18, 4, 12)
        path.lineTo(4, 6)
        path.closeSubpath()
        p.drawPath(path)
        p.drawLine(QPointF(8.5, 12), QPointF(11, 14.5))
        p.drawLine(QPointF(11, 14.5), QPointF(15.5, 9.5))
    elif name == "key":
        p.drawEllipse(QPointF(8, 15.5), 4.5, 4.5)
        p.drawLine(QPointF(11.3, 12.2), QPointF(20, 3.5))
        p.drawLine(QPointF(16.5, 7), QPointF(19, 9.5))
        p.drawLine(QPointF(14, 9.5), QPointF(16, 11.5))
    elif name == "trash":
        p.drawLine(QPointF(4, 7), QPointF(20, 7))
        p.drawLine(QPointF(10, 4), QPointF(14, 4))
        path = QPainterPath()
        path.moveTo(6, 7)
        path.lineTo(7, 20)
        path.lineTo(17, 20)
        path.lineTo(18, 7)
        p.drawPath(path)
    p.end()
    px.setDevicePixelRatio(scale)
    return QIcon(px)


def logo_pixmap(size: int = 40) -> QPixmap:
    """Brand mark: rounded gradient square with a stylised foot-angle glyph."""
    from PyQt6.QtGui import QLinearGradient

    scale = 3
    px = QPixmap(size * scale, size * scale)
    px.fill(Qt.GlobalColor.transparent)
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(scale, scale)
    r = QRectF(0, 0, size, size)
    grad = QLinearGradient(r.topLeft(), r.bottomRight())
    grad.setColorAt(0, QColor("#4F7BFF"))
    grad.setColorAt(1, QColor("#2340C4"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(grad)
    p.drawRoundedRect(r, size * 0.28, size * 0.28)

    # Angle glyph: two lines meeting at a vertex + arc
    s = size / 40.0
    pen = QPen(QColor("white"), 2.6 * s)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen)
    vx, vy = 13 * s, 29 * s
    p.drawLine(QPointF(vx, vy), QPointF(29 * s, 29 * s))
    p.drawLine(QPointF(vx, vy), QPointF(24 * s, 11 * s))
    pen.setWidthF(2.0 * s)
    p.setPen(pen)
    arc = QRectF(vx - 9 * s, vy - 9 * s, 18 * s, 18 * s)
    p.drawArc(arc, 0, 60 * 16)
    p.setBrush(QColor("white"))
    p.setPen(Qt.PenStyle.NoPen)
    p.drawEllipse(QPointF(vx, vy), 2.2 * s, 2.2 * s)
    p.end()
    px.setDevicePixelRatio(scale)
    return px


# ── Global stylesheet ────────────────────────────────────────────────

_ASSET_DIR: str | None = None


def _assets() -> dict[str, str]:
    """Write small SVG glyphs (arrows, check) to a cache dir for QSS url()."""
    import os
    import tempfile

    global _ASSET_DIR
    if _ASSET_DIR is None:
        _ASSET_DIR = os.path.join(tempfile.gettempdir(), "hallux_valgus_theme")
        os.makedirs(_ASSET_DIR, exist_ok=True)
    svgs = {
        "down": f'<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12">'
                f'<path d="M3 4.5l3 3 3-3" fill="none" stroke="{TEXT_2}" stroke-width="1.6" '
                f'stroke-linecap="round" stroke-linejoin="round"/></svg>',
        "up": f'<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 12 12">'
              f'<path d="M3 7.5l3-3 3 3" fill="none" stroke="{TEXT_2}" stroke-width="1.6" '
              f'stroke-linecap="round" stroke-linejoin="round"/></svg>',
        "check": '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 16 16">'
                 '<path d="M4 8.2l2.6 2.6L12 5.4" fill="none" stroke="#ffffff" stroke-width="2" '
                 'stroke-linecap="round" stroke-linejoin="round"/></svg>',
    }
    paths: dict[str, str] = {}
    for name, svg in svgs.items():
        path = os.path.join(_ASSET_DIR, f"{name}.svg")
        with open(path, "w", encoding="utf-8") as f:
            f.write(svg)
        paths[name] = path.replace("\\", "/")
    return paths


def stylesheet() -> str:
    a = _assets()
    return f"""
    * {{
        font-family: "{family()}";
    }}
    QMainWindow, QDialog {{
        background-color: {BG};
        color: {TEXT};
    }}
    QWidget {{
        color: {TEXT};
        font-size: 13px;
    }}
    QLabel {{ background: transparent; }}

    QToolTip {{
        background-color: {TEXT};
        color: white;
        border: none;
        padding: 6px 10px;
        border-radius: 6px;
    }}

    /* ── Typography roles ───────────────────────── */
    QLabel[role="title"] {{ font-size: 22px; font-weight: 700; color: {TEXT}; }}
    QLabel[role="subtitle"] {{ font-size: 13px; color: {TEXT_2}; }}
    QLabel[role="caption"] {{ font-size: 11px; color: {MUTED}; }}
    QLabel[role="overline"] {{
        font-size: 11px; font-weight: 600; color: {MUTED};
        letter-spacing: 0.6px;
    }}
    QLabel[role="section"] {{ font-size: 13px; font-weight: 700; color: {TEXT}; }}
    QLabel[role="field"] {{ font-size: 12px; font-weight: 600; color: {TEXT_2}; }}
    QLabel[role="value"] {{ font-size: 22px; font-weight: 700; color: {TEXT}; }}
    QLabel[role="error"] {{ font-size: 12px; color: {DANGER}; }}

    /* ── Surfaces ───────────────────────────────── */
    QFrame#card {{
        background-color: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 14px;
    }}
    QFrame#divider {{
        background-color: {BORDER};
        border: none;
        max-height: 1px;
        min-height: 1px;
    }}

    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget#qt_scrollarea_viewport {{ background: transparent; }}
    QScrollArea > QWidget > QWidget#scrollContent {{ background: transparent; }}

    /* ── Buttons ────────────────────────────────── */
    QPushButton {{
        background-color: {PRIMARY};
        color: white;
        border: 1px solid {PRIMARY};
        border-radius: 8px;
        padding: 7px 16px;
        font-size: 13px;
        font-weight: 600;
        min-height: 22px;
    }}
    QPushButton:hover {{ background-color: {PRIMARY_HOVER}; border-color: {PRIMARY_HOVER}; }}
    QPushButton:pressed {{ background-color: {PRIMARY_PRESSED}; border-color: {PRIMARY_PRESSED}; }}
    QPushButton:disabled {{
        background-color: #E2E8F0; border-color: #E2E8F0; color: {MUTED};
    }}
    QPushButton:focus {{ outline: none; }}

    QPushButton[variant="secondary"] {{
        background-color: {SURFACE};
        color: {TEXT};
        border: 1px solid {BORDER_STRONG};
    }}
    QPushButton[variant="secondary"]:hover {{
        background-color: {SURFACE_ALT}; border-color: #B4BFCE;
    }}
    QPushButton[variant="secondary"]:pressed {{ background-color: #EEF1F6; }}
    QPushButton[variant="secondary"]:disabled, QPushButton[variant="ghost"]:disabled {{
        background-color: {SURFACE_ALT}; color: {MUTED}; border-color: {BORDER};
    }}

    QPushButton[variant="ghost"] {{
        background-color: transparent;
        color: {TEXT_2};
        border: 1px solid transparent;
    }}
    QPushButton[variant="ghost"]:hover {{ background-color: #EEF1F6; color: {TEXT}; }}

    QPushButton[variant="danger"] {{
        background-color: {DANGER}; border-color: {DANGER}; color: white;
    }}
    QPushButton[variant="danger"]:hover {{ background-color: {DANGER_HOVER}; border-color: {DANGER_HOVER}; }}

    QPushButton[variant="danger-ghost"] {{
        background-color: transparent; color: {TEXT_2};
        border: 1px solid transparent; padding: 4px 10px; font-size: 12px;
    }}
    QPushButton[variant="danger-ghost"]:hover {{
        background-color: {DANGER_SOFT}; color: {DANGER};
    }}

    QPushButton[variant="success"] {{
        background-color: {SUCCESS}; border-color: {SUCCESS}; color: white;
    }}
    QPushButton[variant="success"]:hover {{ background-color: #0B8A5F; border-color: #0B8A5F; }}

    QPushButton[variant="soft"] {{
        background-color: {PRIMARY_SOFT}; border-color: {PRIMARY_SOFT}; color: {PRIMARY};
    }}
    QPushButton[variant="soft"]:hover {{ background-color: #DCE6FF; border-color: #DCE6FF; }}
    QPushButton[variant="soft"]:disabled {{ background-color: #F1F5F9; border-color: #F1F5F9; color: {MUTED}; }}

    QPushButton[size="sm"] {{ padding: 4px 10px; font-size: 12px; border-radius: 7px; min-height: 18px; }}
    QPushButton[size="lg"] {{ padding: 11px 20px; font-size: 14px; border-radius: 10px; }}

    /* ── Inputs ─────────────────────────────────── */
    QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox {{
        background-color: {SURFACE};
        border: 1px solid {BORDER_STRONG};
        border-radius: 8px;
        padding: 6px 10px;
        font-size: 13px;
        selection-background-color: {PRIMARY};
        selection-color: white;
    }}
    QLineEdit:hover, QTextEdit:hover, QComboBox:hover, QSpinBox:hover, QDoubleSpinBox:hover {{
        border-color: #B4BFCE;
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus,
    QSpinBox:focus, QDoubleSpinBox:focus {{
        border: 1px solid {PRIMARY};
    }}
    QLineEdit:disabled, QTextEdit:disabled, QComboBox:disabled {{
        background-color: {SURFACE_ALT}; color: {MUTED}; border-color: {BORDER};
    }}
    QLineEdit[flat="true"] {{
        border: 1px solid transparent;
        border-radius: 6px;
        background: transparent;
        padding: 3px 6px;
        font-weight: 600;
    }}
    QLineEdit[flat="true"]:hover {{ background: {SURFACE_ALT}; border-color: {BORDER}; }}
    QLineEdit[flat="true"]:focus {{ background: {SURFACE}; border-color: {PRIMARY}; }}

    QComboBox {{ padding-right: 28px; }}
    QComboBox::drop-down {{
        subcontrol-origin: padding; subcontrol-position: center right;
        width: 26px; border: none;
    }}
    QComboBox::down-arrow {{
        image: url("{a['down']}");
        width: 12px; height: 12px;
        margin-right: 10px;
    }}
    QComboBox QAbstractItemView {{
        background: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 8px;
        padding: 4px;
        outline: none;
        selection-background-color: {PRIMARY_SOFT};
        selection-color: {TEXT};
    }}
    QSpinBox::up-button, QSpinBox::down-button,
    QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
        width: 18px; border: none; background: transparent;
    }}
    QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
        image: url("{a['up']}"); width: 10px; height: 10px;
    }}
    QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
        image: url("{a['down']}"); width: 10px; height: 10px;
    }}

    /* ── Check / Radio ──────────────────────────── */
    QCheckBox, QRadioButton {{ spacing: 8px; font-size: 13px; background: transparent; }}
    QCheckBox::indicator, QRadioButton::indicator {{
        width: 16px; height: 16px;
        border: 1.5px solid {BORDER_STRONG};
        background-color: {SURFACE};
    }}
    QCheckBox::indicator {{ border-radius: 5px; }}
    QRadioButton::indicator {{ border-radius: 9px; }}
    QCheckBox::indicator:hover, QRadioButton::indicator:hover {{ border-color: {PRIMARY}; }}
    QCheckBox::indicator:checked {{
        background-color: {PRIMARY}; border-color: {PRIMARY};
        image: url("{a['check']}");
    }}
    QRadioButton::indicator:checked {{
        background-color: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
            stop:0 white, stop:0.38 white, stop:0.45 {PRIMARY}, stop:1 {PRIMARY});
        border-color: {PRIMARY};
    }}
    QCheckBox:disabled, QRadioButton:disabled {{ color: {MUTED}; }}

    /* ── Segmented radio (pill toggle) ──────────── */
    QRadioButton[segment="true"] {{
        background-color: transparent;
        border: none;
        border-radius: 7px;
        padding: 5px 10px;
        color: {TEXT_2};
        font-size: 12px;
        font-weight: 600;
    }}
    QRadioButton[segment="true"]::indicator {{ width: 0; height: 0; border: none; }}
    QRadioButton[segment="true"]:checked {{
        background-color: {SURFACE}; color: {TEXT};
    }}
    QFrame#segment {{
        background-color: #EEF1F6; border-radius: 9px; border: none;
    }}

    /* ── Tables ─────────────────────────────────── */
    QTableWidget, QTableView {{
        background-color: {SURFACE};
        border: none;
        gridline-color: transparent;
        selection-background-color: {PRIMARY_SOFT};
        selection-color: {TEXT};
        outline: none;
        font-size: 13px;
    }}
    QTableWidget::item, QTableView::item {{
        padding: 0 12px;
        border-bottom: 1px solid #EEF1F5;
    }}
    QTableWidget::item:hover, QTableView::item:hover {{ background-color: {SURFACE_ALT}; }}
    QTableWidget::item:selected, QTableView::item:selected {{
        background-color: {PRIMARY_SOFT}; color: {TEXT};
    }}
    QHeaderView {{ background: transparent; border: none; }}
    QHeaderView::section {{
        background-color: {SURFACE};
        color: {MUTED};
        padding: 10px 12px;
        border: none;
        border-bottom: 1px solid {BORDER};
        font-size: 12px;
        font-weight: 600;
    }}
    QHeaderView::section:hover {{ color: {TEXT_2}; }}
    QTableCornerButton::section {{ background: {SURFACE}; border: none; }}

    /* ── Group box ──────────────────────────────── */
    QGroupBox {{
        background-color: {SURFACE};
        border: 1px solid {BORDER};
        border-radius: 12px;
        margin-top: 26px;
        padding: 16px 14px 14px 14px;
        font-size: 14px;
        font-weight: 700;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        subcontrol-position: top left;
        left: 4px;
        top: 2px;
        padding: 0 4px;
        color: {TEXT};
    }}
    QGroupBox QLabel {{ font-weight: 400; }}

    /* ── Scrollbars ─────────────────────────────── */
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{
        background: #CBD3DF; border-radius: 3px; min-height: 32px;
    }}
    QScrollBar::handle:vertical:hover {{ background: #A9B4C4; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
    QScrollBar::handle:horizontal {{
        background: #CBD3DF; border-radius: 3px; min-width: 32px;
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}

    /* ── Status bar ─────────────────────────────── */
    QStatusBar {{
        background-color: {SURFACE};
        color: {MUTED};
        border-top: 1px solid {BORDER};
        font-size: 11px;
    }}
    QStatusBar::item {{ border: none; }}

    /* ── Message box ────────────────────────────── */
    QMessageBox {{ background-color: {SURFACE}; }}
    QMessageBox QLabel {{ color: {TEXT}; font-size: 13px; }}
    QMessageBox QPushButton {{ min-width: 84px; }}
    """


def apply(app: QApplication) -> None:
    """Install palette, default font and global stylesheet on the app."""
    app.setStyle("Fusion")
    app.setFont(font(10))

    pal = app.palette()
    pal.setColor(QPalette.ColorRole.Window, QColor(BG))
    pal.setColor(QPalette.ColorRole.Base, QColor(SURFACE))
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(SURFACE_ALT))
    pal.setColor(QPalette.ColorRole.Text, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.WindowText, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.ButtonText, QColor(TEXT))
    pal.setColor(QPalette.ColorRole.Highlight, QColor(PRIMARY))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
    pal.setColor(QPalette.ColorRole.PlaceholderText, QColor(MUTED))
    app.setPalette(pal)

    app.setStyleSheet(stylesheet())


def divider() -> QFrame:
    line = QFrame()
    line.setObjectName("divider")
    line.setFixedHeight(1)
    return line


ICON_SIZE = QSize(18, 18)
