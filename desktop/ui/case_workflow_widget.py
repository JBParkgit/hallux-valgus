"""Single-screen case view for hallux valgus surgery decision support.

Layout:
  Top    - 환자정보 (가로) + 발 선택
  Left   - 좌측 발: 측정버튼, 병력/진찰소견, 측정각도, 수술추천, 최종수술결정
  Center - X-ray 캔버스 (공유)
  Right  - 우측 발: 측정버튼, 병력/진찰소견, 측정각도, 수술추천, 최종수술결정
  Bottom - 메모, 저장/알림톡/EMR 공유 버튼
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from desktop.ui.angle_canvas import LINE_LABELS, LINE_ORDER, AngleCanvas, line_color
from desktop.ui import msgbox, theme
from desktop.core.paths import data_dir

_XRAY_DIR = data_dir("xray_images")


def _section_title(text: str) -> QLabel:
    return theme.label(text, "overline")


def _separator() -> QFrame:
    return theme.divider()


_SEV_EMPTY_SS = (
    f"color: {theme.MUTED}; background-color: {theme.SURFACE_ALT}; "
    f"border: 1px dashed {theme.BORDER_STRONG}; border-radius: 10px; padding: 3px 10px;"
)


def _default_clinical() -> dict[str, Any]:
    return {
        "hypermobility": False,
        "congruent": True,
        "oa_grade": 0,
    }


class CaseWorkflowWidget(QWidget):
    """3-column case widget: left side | shared canvas | right side."""

    case_saved = pyqtSignal()

    SURGERY_OPTIONS = [
        "Chevron 절골술",
        "Scarf 절골술",
        "근위 절골술",
        "Lapidus 절골술",
        "제1MTP 관절유합술",
    ]

    _UNI_TYPES: dict[str, QColor] = {
        k: QColor(theme.ANGLE_COLORS[k]) for k in ("HVA", "IMA", "DMAA")
    }
    _BI_TYPES: dict[str, QColor] = {
        k: QColor(theme.ANGLE_COLORS[k])
        for k in ("L-HVA", "L-IMA", "L-DMAA", "R-HVA", "R-IMA", "R-DMAA")
    }

    def __init__(
        self,
        doctor_name: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._doctor_name = doctor_name
        self._doctor_id = ""
        self._selected_patient: dict[str, Any] | None = None
        self._current_case_id: str | None = None
        self._current_report_url: str = ""
        self._foot_side: str = "bilateral"
        self._algorithm_config: dict[str, Any] | None = None
        self._recommendations: dict[str, dict[str, Any] | None] = {
            "left": None, "right": None,
        }
        self._panels: dict[str, dict[str, Any]] = {}
        self._dirty: bool = False
        # X-ray changed since last upload to the server
        self._xray_dirty: bool = False
        # Viewing another doctor's case → nothing can be changed
        self._read_only: bool = False

        # Building the screen and filling in the patient must not count as an
        # unsaved change (otherwise "새 케이스" asks to discard right away).
        self._loading = True
        self._init_ui()
        self._connect_dirty_signals()
        self._auto_load_patient()
        self._loading = False
        self._clear_dirty()

    def _mark_dirty(self) -> None:
        if getattr(self, "_loading", False):
            return
        self._dirty = True
        self._dirty_label.setText("● 저장되지 않음")
        self._dirty_label.setVisible(True)

    def _clear_dirty(self) -> None:
        self._dirty = False
        self._dirty_label.setText("")
        self._dirty_label.setVisible(False)

    def _connect_dirty_signals(self) -> None:
        """Connect UI change signals to mark unsaved state."""
        self._pt_name.textChanged.connect(self._mark_dirty)
        self._pt_birth.textChanged.connect(self._mark_dirty)
        self._pt_phone.textChanged.connect(self._mark_dirty)
        self._pt_reg.textChanged.connect(self._mark_dirty)
        self._memo_text.textChanged.connect(self._mark_dirty)
        for side in ("left", "right"):
            p = self._panels[side]
            p["hypermobility_cb"].toggled.connect(self._mark_dirty)
            p["congruent_radio"].toggled.connect(self._mark_dirty)
            p["oa_grade"].currentIndexChanged.connect(self._mark_dirty)
            # 임상 소견이 바뀌면 이전 추천은 더 이상 유효하지 않다
            for sig in (p["hypermobility_cb"].toggled, p["congruent_radio"].toggled,
                        p["oa_grade"].currentIndexChanged):
                sig.connect(lambda *_, s=side: self._invalidate_recommendation(s))

    def has_unsaved_changes(self) -> bool:
        """Return True if there are unsaved modifications."""
        return self._dirty

    def confirm_discard(self) -> bool:
        """Ask user to confirm discarding unsaved changes. Returns True if OK to proceed."""
        if not self._dirty:
            return True
        return msgbox.question(
            self, "저장되지 않은 변경사항",
            "저장하지 않은 변경사항이 있습니다.\n계속하면 변경사항이 사라집니다.\n\n계속하시겠습니까?",
        ) == QMessageBox.StandardButton.Yes

    def resizeEvent(self, event) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        self._position_overlay_buttons()

    def eventFilter(self, obj, event) -> bool:  # type: ignore[override]
        from PyQt6.QtCore import QEvent
        if obj is self._angle_canvas and event.type() == QEvent.Type.Resize:
            self._position_overlay_buttons()
        return super().eventFilter(obj, event)

    # ================================================================
    #  UI Building
    # ================================================================

    def _init_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 14, 16, 12)
        outer.setSpacing(12)

        self._build_patient_bar(outer)

        columns = QHBoxLayout()
        columns.setSpacing(12)

        self._build_side_panel("left", columns)
        self._build_center_column(columns)
        self._build_side_panel("right", columns)

        # Build overlay mode buttons on canvas after panels exist
        self._build_mode_buttons("left")
        self._build_mode_buttons("right")

        # Reposition overlays when canvas resizes
        self._angle_canvas.installEventFilter(self)

        outer.addLayout(columns, 1)
        self._build_bottom_bar(outer)

        # Always bilateral: one set of 4 lines per foot
        self._angle_canvas.active_line_changed.connect(self._sync_line_buttons)
        self._angle_canvas.lines_changed.connect(self._on_lines_changed)
        self._angle_canvas.image_changed.connect(self._on_image_changed)
        self._angle_canvas.set_sides(["L-", "R-"])
        self._sync_line_buttons(self._angle_canvas.active_line)
        self._on_lines_changed()

    # ── Patient bar ──────────────────────────────────────────────

    def _build_patient_bar(self, parent_layout: QVBoxLayout) -> None:
        bar = theme.card(shadow=False)
        ly = QHBoxLayout(bar)
        ly.setContentsMargins(18, 12, 18, 12)
        ly.setSpacing(18)

        # Avatar
        avatar = QLabel()
        avatar.setFixedSize(40, 40)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        avatar.setPixmap(theme.icon("user", theme.PRIMARY, 20).pixmap(20, 20))
        avatar.setStyleSheet(f"background-color: {theme.PRIMARY_SOFT}; border-radius: 20px;")
        ly.addWidget(avatar)

        _edit_fields = [
            ("환자명", "_pt_name", 200),
            ("생년월일", "_pt_birth", 110),
            ("전화번호", "_pt_phone", 140),
            ("등록번호", "_pt_reg", 110),
        ]
        for label_text, attr, width in _edit_fields:
            col = QVBoxLayout()
            col.setSpacing(0)
            cap = theme.label(label_text, "caption")
            cap.setContentsMargins(7, 0, 0, 0)
            col.addWidget(cap)
            edit = QLineEdit("-")
            edit.setProperty("flat", True)
            edit.setFixedWidth(width)
            if attr == "_pt_name":
                edit.setStyleSheet("font-size: 16px; font-weight: 700;")
            setattr(self, attr, edit)
            col.addWidget(edit)
            ly.addLayout(col)

        # Age (read-only, auto-calculated)
        age_col = QVBoxLayout()
        age_col.setSpacing(0)
        age_cap = theme.label("나이", "caption")
        age_col.addWidget(age_cap)
        age_row = QHBoxLayout()
        age_row.setSpacing(2)
        self._pt_age = QLabel("-")
        self._pt_age.setStyleSheet("font-weight: 700; font-size: 13px; padding: 3px 0;")
        age_row.addWidget(self._pt_age)
        age_unit = theme.label("세", "caption")
        age_row.addWidget(age_unit)
        age_row.addStretch()
        age_col.addLayout(age_row)
        ly.addLayout(age_col)

        self._dirty_label = QLabel("")
        self._dirty_label.setStyleSheet(theme.pill_style(theme.WARNING, theme.WARNING_SOFT))
        self._dirty_label.setVisible(False)
        ly.addWidget(self._dirty_label, 0, Qt.AlignmentFlag.AlignVCenter)

        self._readonly_label = QLabel("")
        self._readonly_label.setStyleSheet(theme.pill_style(theme.TEXT_2, "#EEF1F6"))
        self._readonly_label.setVisible(False)
        ly.addWidget(self._readonly_label, 0, Qt.AlignmentFlag.AlignVCenter)

        # Recalculate age when birth changes
        self._pt_birth.textChanged.connect(self._on_birth_changed)

        ly.addStretch()

        reload_btn = QPushButton("  환자 불러오기")
        self._reload_btn = reload_btn
        theme.set_variant(reload_btn, "secondary")
        reload_btn.setIcon(theme.icon("refresh", theme.TEXT_2, 16))
        reload_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reload_btn.setToolTip("SMS_Patient.txt 에서 환자 정보를 다시 읽어옵니다")
        reload_btn.clicked.connect(self._auto_load_patient)
        ly.addWidget(reload_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        parent_layout.addWidget(bar)

    # ── Center: Canvas only ──────────────────────────────────────

    def _build_center_column(self, parent_layout: QHBoxLayout) -> None:
        center = QWidget()
        ly = QVBoxLayout(center)
        ly.setContentsMargins(0, 0, 0, 0)
        ly.setSpacing(0)

        # Canvas takes full space
        self._angle_canvas = AngleCanvas()
        self._angle_canvas.angle_measured.connect(self._on_angle_measured)
        self._angle_canvas.angle_reset.connect(self._on_angle_reset)
        ly.addWidget(self._angle_canvas, 1)

        parent_layout.addWidget(center, 1)

    def _build_mode_buttons(self, side: str) -> None:
        """Overlay buttons on the canvas: the 4 lines to draw for this foot."""
        p = self._panels[side]
        p["line_btns"] = {}
        p["clear_btns"] = {}
        _BTN_W = 132
        prefix = "L-" if side == "left" else "R-"

        col = QWidget(self._angle_canvas)
        col.setStyleSheet("background: transparent;")
        col_ly = QVBoxLayout(col)
        col_ly.setContentsMargins(10, 10, 10, 0)
        col_ly.setSpacing(5)

        side_cap = QLabel("좌측 발" if side == "left" else "우측 발")
        side_cap.setStyleSheet(
            "color: rgba(255,255,255,0.55); font-size: 11px; font-weight: 600; padding: 0 2px 2px 2px;"
        )
        side_cap.setAlignment(
            Qt.AlignmentFlag.AlignLeft if side == "left" else Qt.AlignmentFlag.AlignRight
        )
        col_ly.addWidget(side_cap)

        _CLR = 20
        _CLR_HIDDEN_SS = f"""
            QPushButton {{
                background-color: transparent; color: transparent;
                border: none; padding: 0; margin: 0;
                min-height: {_CLR}px; max-height: {_CLR}px;
                min-width: {_CLR}px; max-width: {_CLR}px;
            }}
        """
        _CLR_VISIBLE_SS = f"""
            QPushButton {{
                background-color: rgba(255,255,255,0.14); color: white;
                font-weight: 700; font-size: 12px;
                border-radius: {_CLR // 2}px; border: none;
                padding: 0; margin: 0;
                min-height: {_CLR}px; max-height: {_CLR}px;
                min-width: {_CLR}px; max-width: {_CLR}px;
            }}
            QPushButton:hover {{ background-color: {theme.DANGER}; }}
        """
        for step, key in enumerate(LINE_ORDER, start=1):
            line_id = prefix + key
            color = line_color(line_id).name()
            row = QHBoxLayout()
            row.setSpacing(4)

            btn = QPushButton(f"{step}  {LINE_LABELS[key]}")
            btn.setCheckable(True)
            btn.setFixedSize(_BTN_W, 30)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setToolTip(f"{LINE_LABELS[key]} 그리기 / 다시 그리기")
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: rgba(12,17,28,0.78); color: #CBD5E1;
                    font-weight: 600; font-size: 11px; padding: 0 8px;
                    text-align: left;
                    border-radius: 7px;
                    border: 1px solid rgba(255,255,255,0.10);
                    border-left: 3px solid {color};
                    min-height: 0;
                }}
                QPushButton[done="true"] {{ color: white; }}
                QPushButton:hover {{
                    background-color: rgba(30,40,62,0.92); color: white;
                }}
                QPushButton:checked {{
                    background-color: {color}; color: #0B0F17;
                    border: 1px solid rgba(255,255,255,0.75);
                    border-left: 3px solid white;
                    font-weight: 700;
                }}
                QPushButton:disabled, QPushButton:checked:disabled {{
                    background-color: rgba(12,17,28,0.60); color: rgba(255,255,255,0.45);
                    border: 1px solid rgba(255,255,255,0.06);
                    border-left: 3px solid {color};
                    font-weight: 600;
                }}
            """)
            btn.clicked.connect(lambda checked, lid=line_id: self._select_line(lid))
            p["line_btns"][key] = btn

            clear_btn = QPushButton("×")
            clear_btn.setFixedSize(_CLR, _CLR)
            clear_btn.setStyleSheet(_CLR_HIDDEN_SS)
            clear_btn.setEnabled(False)
            clear_btn.setToolTip(f"{LINE_LABELS[key]} 지우기")
            clear_btn.clicked.connect(lambda checked, lid=line_id: self._angle_canvas.clear_line(lid))
            clear_btn._ss_visible = _CLR_VISIBLE_SS  # type: ignore[attr-defined]
            clear_btn._ss_hidden = _CLR_HIDDEN_SS  # type: ignore[attr-defined]
            p["clear_btns"][key] = clear_btn

            # Mirror order on the right edge so the clear badge sits on the inside
            if side == "left":
                row.addWidget(btn)
                row.addWidget(clear_btn)
            else:
                row.addWidget(clear_btn)
                row.addWidget(btn)

            col_ly.addLayout(row)

        col_ly.addStretch()
        col.adjustSize()

        # Store reference to position on resize
        if side == "left":
            self._left_overlay = col
        else:
            self._right_overlay = col

        col.show()
        self._position_overlay_buttons()

    def _position_overlay_buttons(self) -> None:
        """Position overlay button columns at top-left and top-right of canvas."""
        if hasattr(self, "_left_overlay"):
            self._left_overlay.move(4, 4)
            self._left_overlay.adjustSize()
        if hasattr(self, "_right_overlay"):
            w = self._angle_canvas.width()
            ow = self._right_overlay.sizeHint().width()
            self._right_overlay.move(w - ow - 4, 4)
            self._right_overlay.adjustSize()

    # ── Side panel (left or right foot) ──────────────────────────

    def _build_side_panel(self, side: str, parent_layout: QHBoxLayout) -> None:
        p: dict[str, Any] = {}
        side_kr = "좌측" if side == "left" else "우측"
        prefix = "L-" if side == "left" else "R-"

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setMinimumWidth(270)
        scroll.setMaximumWidth(330)

        holder = QWidget()
        holder.setObjectName("scrollContent")
        h_ly = QVBoxLayout(holder)
        h_ly.setContentsMargins(0, 0, 0, 0)

        panel = theme.card(shadow=False)
        h_ly.addWidget(panel)
        h_ly.addStretch()

        ly = QVBoxLayout(panel)
        ly.setContentsMargins(18, 16, 18, 18)
        ly.setSpacing(8)

        # ── Header ───────────────────────────────────────────────
        head = QHBoxLayout()
        side_title = QLabel(f"{side_kr} 발")
        side_title.setStyleSheet("font-size: 16px; font-weight: 700;")
        head.addWidget(side_title)
        side_tag = theme.label("LEFT" if side == "left" else "RIGHT", "caption")
        side_tag.setStyleSheet(f"color: {theme.MUTED}; font-size: 10px; font-weight: 700; padding-top: 3px;")
        head.addWidget(side_tag)
        head.addStretch()
        sev_badge = QLabel("중증도 미판정")
        sev_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sev_badge.setStyleSheet(_SEV_EMPTY_SS)
        head.addWidget(sev_badge)
        p["severity_badge"] = sev_badge
        ly.addLayout(head)

        ly.addSpacing(4)
        ly.addWidget(_separator())
        ly.addSpacing(4)

        # ── 1. 측정 각도 ────────────────────────────────────────
        ly.addWidget(_section_title("측정 각도"))
        p["angle_displays"] = {}
        hints = {"HVA": "정상 < 15°", "IMA": "정상 < 9°", "DMAA": "정상 < 10°"}
        names = {"HVA": "무지외반각", "IMA": "중족골간각", "DMAA": "원위관절면각"}
        for base in ("HVA", "IMA", "DMAA"):
            color = theme.ANGLE_COLORS[prefix + base]
            tile = QFrame()
            tile.setObjectName("angleTile")
            tile.setStyleSheet(
                f"QFrame#angleTile {{ background-color: {theme.SURFACE_ALT}; "
                f"border: 1px solid {theme.BORDER}; border-radius: 10px; }}"
            )
            t_ly = QHBoxLayout(tile)
            t_ly.setContentsMargins(0, 8, 12, 8)
            t_ly.setSpacing(10)

            bar = QFrame()
            bar.setFixedSize(4, 30)
            bar.setStyleSheet(f"background-color: {color}; border-radius: 2px; border: none;")
            t_ly.addSpacing(8)
            t_ly.addWidget(bar)

            text_col = QVBoxLayout()
            text_col.setSpacing(0)
            nlbl = QLabel(base)
            nlbl.setStyleSheet("font-size: 13px; font-weight: 700;")
            text_col.addWidget(nlbl)
            hlbl = theme.label(f"{names[base]} · {hints[base]}", "caption")
            text_col.addWidget(hlbl)
            t_ly.addLayout(text_col, 1)

            vlbl = QLabel("-- °")
            vlbl.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            vlbl.setStyleSheet("font-size: 20px; font-weight: 700;")
            t_ly.addWidget(vlbl)
            p["angle_displays"][base] = vlbl
            ly.addWidget(tile)

        ly.addSpacing(6)

        # ── 2. 임상 소견 ───────────────────────────────────────────
        ly.addWidget(_section_title("임상 소견"))

        hyper_cb = QCheckBox("제1중족골 과운동성")
        ly.addWidget(hyper_cb)
        p["hypermobility_cb"] = hyper_cb
        ly.addSpacing(2)

        ly.addWidget(theme.label("관절 일치성", "field"))
        seg = QFrame()
        seg.setObjectName("segment")
        seg_ly = QHBoxLayout(seg)
        seg_ly.setContentsMargins(3, 3, 3, 3)
        seg_ly.setSpacing(2)
        cong_r = QRadioButton("Congruent")
        incong_r = QRadioButton("Incongruent")
        for r in (cong_r, incong_r):
            r.setProperty("segment", True)
            r.setCursor(Qt.CursorShape.PointingHandCursor)
            seg_ly.addWidget(r, 1)
        cong_r.setChecked(True)
        cong_group = QButtonGroup(self)
        cong_group.addButton(cong_r)
        cong_group.addButton(incong_r)
        ly.addWidget(seg)
        p["congruent_radio"] = cong_r
        p["incongruent_radio"] = incong_r
        ly.addSpacing(2)

        ly.addWidget(theme.label("골관절염", "field"))
        oa_combo = QComboBox()
        oa_combo.addItems(["None", "Mild", "Moderate", "Severe"])
        ly.addWidget(oa_combo)
        p["oa_grade"] = oa_combo

        ly.addSpacing(6)

        # ── 3. 수술 추천 ────────────────────────────────────────
        ly.addWidget(_section_title("수술 추천"))

        rec_box = QFrame()
        rec_box.setObjectName("recBox")
        rec_box.setStyleSheet(
            f"QFrame#recBox {{ background-color: {theme.PRIMARY_SOFT}; "
            f"border: 1px solid #D6E0FF; border-radius: 10px; }}"
        )
        rb_ly = QVBoxLayout(rec_box)
        rb_ly.setContentsMargins(12, 12, 12, 12)
        rb_ly.setSpacing(4)

        rec_lbl = QLabel("-")
        rec_lbl.setStyleSheet(f"font-size: 15px; font-weight: 700; color: {theme.PRIMARY_PRESSED};")
        rec_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rec_lbl.setWordWrap(True)
        rb_ly.addWidget(rec_lbl)
        p["rec_surgery_lbl"] = rec_lbl

        addon_lbl = QLabel("")
        addon_lbl.setStyleSheet(f"font-size: 13px; font-weight: 600; color: {theme.PRIMARY};")
        addon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rb_ly.addWidget(addon_lbl)
        p["addon_lbl"] = addon_lbl

        calc_btn = QPushButton("  추천 계산")
        calc_btn.setIcon(theme.icon("sparkle", "#FFFFFF", 16))
        calc_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        calc_btn.clicked.connect(lambda checked=False, s=side: self._run_algorithm(s))
        rb_ly.addSpacing(4)
        rb_ly.addWidget(calc_btn)
        p["calc_btn"] = calc_btn
        ly.addWidget(rec_box)

        ly.addSpacing(6)

        # ── 4. 최종 수술 결정 ────────────────────────────────────
        ly.addWidget(_section_title("최종 수술 결정"))

        agree_radio = QRadioButton("추천 수술에 동의")
        agree_radio.setChecked(True)
        disagree_radio = QRadioButton("다른 수술 선택")
        group = QButtonGroup(self)
        group.addButton(agree_radio)
        group.addButton(disagree_radio)
        ly.addWidget(agree_radio)
        ly.addWidget(disagree_radio)
        p["agree_radio"] = agree_radio
        p["disagree_radio"] = disagree_radio

        override_surgery = QComboBox()
        override_surgery.addItems(self.SURGERY_OPTIONS)
        override_surgery.setEnabled(False)
        ly.addWidget(override_surgery)
        p["override_surgery"] = override_surgery

        override_reason = QTextEdit()
        override_reason.setPlaceholderText("변경 사유를 입력하세요")
        override_reason.setEnabled(False)
        override_reason.setMaximumHeight(64)
        ly.addWidget(override_reason)
        p["override_reason"] = override_reason

        disagree_radio.toggled.connect(override_surgery.setEnabled)
        disagree_radio.toggled.connect(override_reason.setEnabled)

        scroll.setWidget(holder)
        p["container"] = scroll

        self._panels[side] = p
        parent_layout.addWidget(scroll)

    # ── Bottom bar ───────────────────────────────────────────────

    def _build_bottom_bar(self, parent_layout: QVBoxLayout) -> None:
        bar = theme.card(shadow=False)
        bar_ly = QHBoxLayout(bar)
        bar_ly.setContentsMargins(16, 10, 16, 10)
        bar_ly.setSpacing(12)

        memo_col = QVBoxLayout()
        memo_col.setSpacing(4)
        memo_col.addWidget(theme.label("메모", "field"))
        self._memo_text = QTextEdit()
        self._memo_text.setFixedHeight(44)
        self._memo_text.setPlaceholderText("추가 참고 사항...")
        memo_col.addWidget(self._memo_text)
        bar_ly.addLayout(memo_col, 1)

        status_col = QVBoxLayout()
        status_col.setSpacing(2)
        status_col.addStretch()
        self._send_status_lbl = QLabel("")
        self._send_status_lbl.setStyleSheet(f"color: {theme.TEXT_2}; font-size: 12px;")
        self._send_status_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        status_col.addWidget(self._send_status_lbl)
        self._report_url_lbl = QLabel("")
        self._report_url_lbl.setVisible(False)
        self._copy_status_lbl = QLabel("")
        self._copy_status_lbl.setStyleSheet(f"color: {theme.SUCCESS}; font-size: 11px;")
        self._copy_status_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        status_col.addWidget(self._copy_status_lbl)
        status_col.addStretch()
        bar_ly.addLayout(status_col)

        for label, icon_name, variant, handler, attr in [
            ("EMR 복사", "copy", "secondary", self._copy_to_emr, "_emr_btn"),
            ("알림톡 발송", "send", "secondary", self._save_and_send, "_send_btn"),
            ("저장", "save", "", self._save_only, "_save_btn"),
        ]:
            btn = QPushButton(f"  {label}")
            if variant:
                theme.set_variant(btn, variant)
            icon_color = theme.TEXT_2 if variant else "#FFFFFF"
            btn.setIcon(theme.icon(icon_name, icon_color, 16))
            btn.setMinimumHeight(40)
            btn.setMinimumWidth(110 if variant else 120)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(handler)
            setattr(self, attr, btn)
            bar_ly.addWidget(btn, 0, Qt.AlignmentFlag.AlignBottom)

        parent_layout.addWidget(bar)

    # ================================================================
    #  Patient loading
    # ================================================================

    def _auto_load_patient(self) -> None:
        try:
            from desktop.core.patient_parser import calculate_age, load_patients
            patients = load_patients()
            if patients:
                p = patients[0]
                self._selected_patient = p
                self._pt_name.setText(p.get("name", "-"))
                self._pt_birth.setText(p.get("birth", "-"))
                self._pt_phone.setText(p.get("phone", "-"))
                self._pt_reg.setText(p.get("reg_no", "-"))
                try:
                    self._pt_age.setText(str(calculate_age(p.get("birth", ""))))
                except Exception:
                    self._pt_age.setText("-")
            else:
                self._set_demo_patient()
        except Exception:
            self._set_demo_patient()

    def _set_demo_patient(self) -> None:
        self._selected_patient = {
            "name": "(환자 없음)", "birth": "-", "phone": "-",
            "reg_no": "-", "age": 0,
        }
        try:
            from desktop.core.patient_parser import DEFAULT_PATIENT_FILE
            file_exists = os.path.exists(DEFAULT_PATIENT_FILE)
        except Exception:
            file_exists = False
        # 파일이 있는데 읽은 환자가 없으면 '없음'이 아니라 형식 문제임을 알린다
        self._pt_name.setText(
            "(환자 정보 읽기 실패)" if file_exists else "(SMS_Patient.txt 없음)"
        )
        self._pt_name.setCursorPosition(0)
        for lbl in (self._pt_birth, self._pt_phone, self._pt_age, self._pt_reg):
            lbl.setText("-")

    def _on_birth_changed(self, text: str) -> None:
        """Recalculate age when birth date is edited."""
        try:
            from desktop.core.patient_parser import calculate_age
            age = calculate_age(text.strip())
            self._pt_age.setText(str(age))
        except Exception:
            self._pt_age.setText("-")

    def _get_patient_from_fields(self) -> dict[str, str]:
        """Read current patient info from editable fields."""
        return {
            "name": self._pt_name.text().strip(),
            "birth": self._pt_birth.text().strip(),
            "phone": self._pt_phone.text().strip(),
            "reg_no": self._pt_reg.text().strip(),
        }

    # ================================================================
    #  Foot side management
    # ================================================================

    def _on_foot_side_changed(self, index: int) -> None:
        """For backward compatibility with load_case. Always bilateral now."""
        pass

    # ================================================================
    #  Canvas / angle mode interaction
    # ================================================================

    def _measurement_name(self, side: str, base: str) -> str:
        """Get canvas measurement type name for a side + base angle."""
        prefix = "L-" if side == "left" else "R-"
        return f"{prefix}{base}"

    def _select_line(self, line_id: str) -> None:
        """Overlay button click: draw (or redraw) this line next."""
        self._angle_canvas.active_line = line_id
        self._sync_line_buttons(self._angle_canvas.active_line)
        self._angle_canvas.setFocus()

    def _sync_line_buttons(self, active_line: str) -> None:
        for side, prefix in (("left", "L-"), ("right", "R-")):
            p = self._panels.get(side)
            if not p or "line_btns" not in p:
                continue
            for key, btn in p["line_btns"].items():
                btn.setChecked(prefix + key == active_line)

    def _on_lines_changed(self) -> None:
        """Refresh line buttons (done state, clear badges) after any line change."""
        for side, prefix in (("left", "L-"), ("right", "R-")):
            p = self._panels.get(side)
            if not p or "line_btns" not in p:
                continue
            for key, btn in p["line_btns"].items():
                done = self._angle_canvas.has_line(prefix + key)
                if btn.property("done") != done:
                    btn.setProperty("done", done)
                    theme.repolish(btn)
                self._show_clear_btn(p["clear_btns"][key], done)
        self._mark_dirty()

    def _resolve_side_and_base(self, name: str) -> tuple[str | None, str | None]:
        """Map measurement type name to (side, base_angle)."""
        if name.startswith("L-"):
            return "left", name[2:]
        elif name.startswith("R-"):
            return "right", name[2:]
        else:
            side = self._foot_side if self._foot_side != "bilateral" else "left"
            return side, name

    @staticmethod
    def _show_clear_btn(btn: QPushButton, show: bool) -> None:
        """Show/hide clear badge via style (keeps layout space reserved)."""
        if show:
            btn.setStyleSheet(btn._ss_visible)  # type: ignore[attr-defined]
            btn.setEnabled(True)
        else:
            btn.setStyleSheet(btn._ss_hidden)  # type: ignore[attr-defined]
            btn.setEnabled(False)

    def _on_angle_measured(self, name: str, angle: float) -> None:
        self._mark_dirty()
        side, base = self._resolve_side_and_base(name)
        if side and base:
            p = self._panels.get(side)
            if p and base in p["angle_displays"]:
                p["angle_displays"][base].setText(f"{angle:.1f}°")
            self._invalidate_recommendation(side)
            self._update_realtime_severity(side)

    def _on_angle_reset(self, name: str) -> None:
        self._mark_dirty()
        side, base = self._resolve_side_and_base(name)
        if side and base:
            p = self._panels.get(side)
            if p and base in p["angle_displays"]:
                p["angle_displays"][base].setText("-- °")
            self._invalidate_recommendation(side)
            self._update_realtime_severity(side)

    def _invalidate_recommendation(self, side: str) -> None:
        """Drop the side's recommendation after its angles or clinical findings change.

        A recommendation computed from old values must not stay on screen or be
        saved/sent; the doctor has to press '수술 추천' again.
        """
        if self._loading or self._recommendations.get(side) is None:
            return
        self._recommendations[side] = None
        p = self._panels.get(side)
        if p:
            p["rec_surgery_lbl"].setText("값이 바뀌었습니다 · 다시 추천받아 주세요")
            p["addon_lbl"].setText("")
            self._update_realtime_severity(side)

    def _stale_recommendation_sides(self) -> list[str]:
        """Sides measured (HVA or IMA) that would be saved as '동의' without a current recommendation."""
        stale = []
        for side in self._get_active_sides():
            angles = self._get_angles_for_side(side)
            measured = angles.get("hva") is not None or angles.get("ima") is not None
            agreed = self._panels[side]["agree_radio"].isChecked()
            if measured and agreed and self._recommendations.get(side) is None:
                stale.append(side)
        return stale

    def _update_realtime_severity(self, side: str) -> None:
        """Update severity badge once HVA and IMA are measured."""
        p = self._panels.get(side)
        if not p:
            return
        angles = self._get_angles_for_side(side)
        hva = angles.get("hva")
        ima = angles.get("ima")
        if hva is None or ima is None:
            p["severity_badge"].setText("중증도 미판정")
            p["severity_badge"].setStyleSheet(_SEV_EMPTY_SS)
            return
        # Same rule as the recommendation, with this doctor's thresholds
        from desktop.core.algorithm import classify_severity
        if self._algorithm_config is None:
            self.reload_algorithm_config()
        sev = classify_severity(hva, ima, self._algorithm_config)
        sev_kr = {"mild": "경증", "moderate": "중등도", "severe": "중증"}[sev]
        p["severity_badge"].setText(sev_kr)
        p["severity_badge"].setStyleSheet(theme.severity_pill_style(sev_kr))

    def _on_image_changed(self) -> None:
        self._xray_dirty = True
        self._mark_dirty()

    def _set_read_only(self, read_only: bool, owner_name: str = "") -> None:
        """Lock every editing control when viewing another doctor's case."""
        self._read_only = read_only
        editable = not read_only
        self._readonly_label.setText(f"{owner_name} 선생님 케이스 · 읽기 전용" if read_only else "")
        self._readonly_label.setVisible(read_only)
        self._angle_canvas.set_read_only(read_only)

        for w in (self._pt_name, self._pt_birth, self._pt_phone, self._pt_reg):
            w.setReadOnly(read_only)
        for w in (self._reload_btn, self._save_btn, self._send_btn, self._memo_text):
            w.setEnabled(editable)
        for p in self._panels.values():
            for key in ("hypermobility_cb", "congruent_radio", "incongruent_radio", "oa_grade",
                        "calc_btn", "agree_radio", "disagree_radio"):
                p[key].setEnabled(editable)
            override = editable and p["disagree_radio"].isChecked()
            p["override_surgery"].setEnabled(override)
            p["override_reason"].setEnabled(override)
            for btn in p.get("line_btns", {}).values():
                btn.setEnabled(editable)
            for key, btn in p.get("clear_btns", {}).items():
                self._show_clear_btn(btn, editable and btn.isEnabled())
        if editable:
            self._on_lines_changed()

    def _paste_xray(self) -> None:
        if self._read_only:
            return
        if self._angle_canvas.paste_from_clipboard():
            self._mark_dirty()
        else:
            msgbox.information(
                self, "붙여넣기",
                "클립보드에 이미지가 없습니다.\nPACS에서 X-ray를 복사한 후 다시 시도하세요.",
            )

    # ================================================================
    #  Algorithm
    # ================================================================

    def reload_algorithm_config(self) -> None:
        """Load the logged-in doctor's settings (server first, this PC's copy if offline)."""
        try:
            from desktop.core.algorithm_config import load_config
            if self._doctor_id:
                self._algorithm_config = load_config(self._doctor_id)
        except Exception:
            # keep the last good config rather than silently falling back to defaults
            pass
        self._apply_surgery_list()
        if self._algorithm_config is not None:
            for side in ("left", "right"):
                if self._recommendations.get(side) is None:
                    self._update_realtime_severity(side)

    def _apply_surgery_list(self) -> None:
        """'다른 수술 선택' 목록 = 이 의사가 설정에서 관리하는 수술명."""
        from desktop.core.algorithm_config import DEFAULT_SURGERIES
        cfg = self._algorithm_config or {}
        surgeries = [s for s in cfg.get("surgeries", DEFAULT_SURGERIES) if s] or list(DEFAULT_SURGERIES)
        for p in self._panels.values():
            combo = p["override_surgery"]
            current = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(surgeries)
            if current and current not in surgeries and combo.isEnabled():
                combo.addItem(current)
            idx = combo.findText(current)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)

    def _get_angles_for_side(self, side: str) -> dict[str, float | None]:
        prefix = "L-" if side == "left" else "R-"
        return {
            "hva": self._angle_canvas.get_angle(f"{prefix}HVA"),
            "ima": self._angle_canvas.get_angle(f"{prefix}IMA"),
            "dmaa": self._angle_canvas.get_angle(f"{prefix}DMAA"),
        }

    def _get_clinical_for_side(self, side: str) -> dict[str, Any]:
        p = self._panels[side]
        return {
            "hypermobility": p["hypermobility_cb"].isChecked(),
            "congruent": p["congruent_radio"].isChecked(),
            "oa_grade": p["oa_grade"].currentIndex(),
        }

    def _set_clinical_for_side(self, side: str, data: dict[str, Any]) -> None:
        p = self._panels[side]
        p["hypermobility_cb"].setChecked(data.get("hypermobility", False))
        if data.get("congruent", True):
            p["congruent_radio"].setChecked(True)
        else:
            p["incongruent_radio"].setChecked(True)
        p["oa_grade"].setCurrentIndex(data.get("oa_grade", 0))

    def _run_algorithm(self, side: str) -> None:
        angles = self._get_angles_for_side(side)
        hva = angles.get("hva")
        ima = angles.get("ima")

        # HVA와 IMA는 판정에 둘 다 필요하다. 미측정 값을 0°로 간주하면
        # 중증도가 실제보다 낮게 나올 수 있으므로 판정하지 않는다.
        missing = [name for name, val in (("HVA", hva), ("IMA", ima)) if val is None]
        if missing:
            msgbox.warning(
                self, "각도 미측정",
                f"{', '.join(missing)} 각도를 먼저 측정해 주세요.\n"
                "수술 추천에는 HVA와 IMA가 모두 필요합니다.",
            )
            return

        clinical = self._get_clinical_for_side(side)

        try:
            from desktop.core.algorithm import recommend_surgery

            # Always use the doctor's latest settings (may have changed on another PC)
            self.reload_algorithm_config()

            patient = self._get_patient_from_fields()
            try:
                from desktop.core.patient_parser import calculate_age
                age = calculate_age(patient.get("birth", ""))
            except Exception:
                age = None

            oa_labels = ["none", "mild", "moderate", "severe"]
            oa_val = oa_labels[clinical.get("oa_grade", 0)]

            result = recommend_surgery(
                hva=hva,
                ima=ima,
                dmaa=angles.get("dmaa"),
                age=age,
                hypermobility=clinical.get("hypermobility", False),
                joint_congruency="incongruent" if not clinical.get("congruent", True) else "congruent",
                osteoarthritis=oa_val,
                previous_surgery=False,
                config=self._algorithm_config,
            )
            self._recommendations[side] = {
                "severity": result["severity"],
                "surgery": result["recommended_surgery"],
                "addon_surgery": result.get("additional_surgery") or "",
                "reasons": result["reason"],
            }
        except ImportError:
            severity = "mild" if hva < 30 else ("moderate" if hva < 40 else "severe")
            self._recommendations[side] = {
                "severity": severity,
                "surgery": "Chevron 절골술" if severity == "mild" else "Scarf 절골술",
                "addon_surgery": "",
                "reasons": [f"HVA {hva:.1f}°, IMA {ima:.1f}°"],
            }

        self._update_recommendation_display(side)

    def _update_recommendation_display(self, side: str) -> None:
        p = self._panels.get(side)
        rec = self._recommendations.get(side)
        if not p or not rec:
            return

        sev_raw = rec.get("severity", "moderate")
        sev_map = {"mild": "경증", "moderate": "중등도", "severe": "중증"}
        sev_kr = sev_map.get(sev_raw, sev_raw)
        p["severity_badge"].setText(sev_kr)
        p["severity_badge"].setStyleSheet(theme.severity_pill_style(sev_kr))
        surgery_text = rec.get("surgery", "-")
        p["rec_surgery_lbl"].setText(surgery_text)
        addon = rec.get("addon_surgery", "")
        if addon:
            p["addon_lbl"].setText(f"+ {addon}")
        else:
            p["addon_lbl"].setText("")


    # ================================================================
    #  Save & Send
    # ================================================================

    def _get_active_sides(self) -> list[str]:
        if self._foot_side == "bilateral":
            return ["left", "right"]
        return [self._foot_side]

    def _get_final_surgery(self, side: str) -> tuple[str, str | None]:
        p = self._panels.get(side, {})
        rec = self._recommendations.get(side) or {}
        if p.get("agree_radio") and p["agree_radio"].isChecked():
            final = rec.get("surgery", "")
            addon = rec.get("addon_surgery", "")
            if addon:
                final += f" + {addon}"
            return final, None
        else:
            return (
                p["override_surgery"].currentText() if p.get("override_surgery") else "",
                (p["override_reason"].toPlainText().strip() or None) if p.get("override_reason") else None,
            )

    def _save_case(self) -> str | None:
        if self._read_only:
            msgbox.warning(self, "저장 불가", "다른 선생님의 케이스는 수정할 수 없습니다.")
            return None
        stale = self._stale_recommendation_sides()
        if stale:
            names = ", ".join({"left": "좌측", "right": "우측"}[s] for s in stale)
            if msgbox.question(
                self, "수술 추천 필요",
                f"{names} 발은 각도를 측정했지만 현재 값으로 받은 수술 추천이 없습니다.\n"
                "(측정값이나 임상 소견이 바뀌면 이전 추천은 지워집니다.)\n\n"
                "추천 없이 저장하시겠습니까?",
            ) != QMessageBox.StandardButton.Yes:
                return None
        patient = self._get_patient_from_fields()
        try:
            from desktop.core.patient_parser import calculate_age
            age = calculate_age(patient.get("birth", ""))
        except Exception:
            age = 0

        sides = self._get_active_sides()
        primary = sides[0]
        primary_angles = self._get_angles_for_side(primary)
        primary_rec = self._recommendations.get(primary) or {}
        primary_final, primary_override = self._get_final_surgery(primary)
        primary_clinical = self._get_clinical_for_side(primary)

        case_record: dict[str, Any] = {
            "patientName": patient.get("name", ""),
            "patientBirth": patient.get("birth", ""),
            "patientPhone": patient.get("phone", ""),
            "patientRegNo": patient.get("reg_no", ""),
            "patientAge": age,
            "hvaAngle": primary_angles.get("hva"),
            "imaAngle": primary_angles.get("ima"),
            "dmaaAngle": primary_angles.get("dmaa"),
            "hypermobility": primary_clinical.get("hypermobility", False),
            "jointCongruency": "congruent" if primary_clinical.get("congruent", True) else "incongruent",
            "osteoarthritis": self._panels[primary]["oa_grade"].currentText().lower(),
            "clinicalNotes": self._memo_text.toPlainText().strip() or None,
            "severity": primary_rec.get("severity"),
            "algorithmResult": primary_rec.get("surgery"),
            "algorithmReason": json.dumps(primary_rec.get("reasons", []), ensure_ascii=False),
            "finalDecision": primary_final,
            "overrideReason": primary_override,
        }

        angle_data: dict[str, Any] = {
            "foot_side": self._foot_side,
            "measurements": self._angle_canvas.get_measurements_data(),
            "clinical": {s: self._get_clinical_for_side(s) for s in sides},
        }
        for s in sides:
            s_angles = self._get_angles_for_side(s)
            s_rec = self._recommendations.get(s) or {}
            s_final, s_override = self._get_final_surgery(s)
            angle_data[f"{s}_surgery"] = {
                "angles": s_angles,
                "severity": s_rec.get("severity"),
                "algorithm_result": s_rec.get("surgery"),
                "addon_surgery": s_rec.get("addon_surgery") or "",
                "reasons": s_rec.get("reasons", []),
                "final_decision": s_final,
                "override_reason": s_override,
            }

        case_record["angleData"] = json.dumps(angle_data, ensure_ascii=False)

        from desktop.core import api_client
        try:
            if self._current_case_id:
                saved = api_client.update_case(self._current_case_id, case_record)
            else:
                saved = api_client.create_case(case_record)
                self._current_case_id = saved["id"]
        except api_client.ApiError as e:
            msgbox.critical(self, "저장 실패", e.message)
            return None
        case_id = saved["id"]
        self._current_report_url = saved.get("reportUrl", "")
        self._report_url_lbl.setText(self._current_report_url)
        self._clear_dirty()

        # X-ray → server (only when it changed)
        if self._xray_dirty and self._angle_canvas.has_image():
            try:
                api_client.upload_xray(case_id, self._angle_canvas.raw_image_png() or b"")
                self._xray_dirty = False
            except api_client.ApiError as e:
                self._mark_dirty()
                msgbox.warning(
                    self, "X-ray 업로드 실패",
                    "케이스는 저장되었지만 X-ray 이미지를 서버에 올리지 못했습니다.\n"
                    f"{e.message}\n\n다시 저장하면 재시도합니다.",
                )

        # Local copies on this PC (raw = cache, annotated = for reference)
        try:
            os.makedirs(_XRAY_DIR, exist_ok=True)
            self._angle_canvas.save_raw_image(os.path.join(_XRAY_DIR, f"{case_id}.png"))
            self._angle_canvas.save_image_to_file(os.path.join(_XRAY_DIR, f"{case_id}_annotated.png"))
        except Exception:
            pass
        return case_id

    def _save_only(self) -> None:
        case_id = self._save_case()
        if case_id:
            self._send_status_lbl.setText("✓ 저장 완료")
            self._send_status_lbl.setStyleSheet(f"color: {theme.SUCCESS}; font-size: 12px; font-weight: 600;")
            self.case_saved.emit()
            msgbox.information(self, "저장 완료", "케이스가 성공적으로 저장되었습니다.")

    def _save_and_send(self) -> None:
        case_id = self._save_case()
        if case_id:
            self._send_status_lbl.setText("저장 완료. 알림톡 발송 중...")
            self._send_status_lbl.setStyleSheet(f"color: {theme.TEXT_2}; font-size: 12px;")
            QApplication.processEvents()
            self._send_alimtalk()
            self.case_saved.emit()

    def _send_alimtalk(self) -> None:
        if self._read_only:
            return
        patient = self._get_patient_from_fields()
        phone = patient.get("phone", "")
        if not phone or phone == "-":
            msgbox.warning(self, "발송 실패", "환자 전화번호가 없습니다.")
            return
        if not self._current_case_id and not self._save_case():
            return

        self._send_status_lbl.setText("발송 중...")
        self._send_status_lbl.setStyleSheet(f"color: {theme.TEXT_2}; font-size: 12px;")
        QApplication.processEvents()

        from desktop.core.alimtalk import send_case_alimtalk
        result = send_case_alimtalk(self._current_case_id)
        if result.get("success"):
            self._send_status_lbl.setText("✓ 알림톡 발송 완료")
            self._send_status_lbl.setStyleSheet(f"color: {theme.SUCCESS}; font-size: 12px; font-weight: 600;")
        else:
            self._send_status_lbl.setText("알림톡 발송 실패")
            self._send_status_lbl.setStyleSheet(f"color: {theme.DANGER}; font-size: 12px; font-weight: 600;")
            msgbox.warning(self, "알림톡 발송 실패", result.get("error", "알 수 없는 오류"))

    # ================================================================
    #  EMR Copy
    # ================================================================

    def _copy_to_emr(self) -> None:
        patient = self._get_patient_from_fields()
        foot_labels = {"left": "좌측", "right": "우측", "bilateral": "양측"}

        lines = [
            "[무지외반증 수술 결정]",
            f"환자: {patient.get('name', '-')} ({patient.get('birth', '-')})",
            f"등록번호: {patient.get('reg_no', '-')}",
            f"측정 발: {foot_labels.get(self._foot_side, '')}",
            "",
        ]

        for side in self._get_active_sides():
            angles = self._get_angles_for_side(side)
            clinical = self._get_clinical_for_side(side)
            rec = self._recommendations.get(side) or {}
            final, override = self._get_final_surgery(side)

            sev_map = {"mild": "경증", "moderate": "중등도", "severe": "중증"}
            severity_kr = sev_map.get(rec.get("severity", ""), "-")

            side_label = {"left": "좌측", "right": "우측"}.get(side, "")
            tag = f" ({side_label})" if self._foot_side == "bilateral" else ""

            hva_s = f"{angles['hva']:.1f}°" if angles.get("hva") else "미측정"
            ima_s = f"{angles['ima']:.1f}°" if angles.get("ima") else "미측정"
            dmaa_s = f"{angles['dmaa']:.1f}°" if angles.get("dmaa") else "미측정"

            oa_labels = ["None", "Mild", "Moderate", "Severe"]
            oa_idx = clinical.get("oa_grade", 0)
            oa_text = oa_labels[oa_idx] if oa_idx < len(oa_labels) else "-"

            lines.extend([
                f"< X-ray 각도{tag} >",
                f"  HVA: {hva_s}",
                f"  IMA: {ima_s}",
                f"  DMAA: {dmaa_s}",
                f"  중증도: {severity_kr}",
                "",
                f"< 임상 소견{tag} >",
                f"  과운동성: {'있음' if clinical.get('hypermobility') else '없음'}",
                f"  관절 일치성: {'Congruent' if clinical.get('congruent', True) else 'Incongruent'}",
                f"  골관절염: {oa_text}",
            ])

            lines.extend([
                "",
                f"< 수술 결정{tag} >",
                f"  알고리즘 추천: {rec.get('surgery', '-')}",
                f"  최종 결정: {final}",
            ])
            if override:
                lines.append(f"  변경 사유: {override}")
            lines.append("")

        memo = self._memo_text.toPlainText().strip()
        if memo:
            lines.extend(["< 메모 >", f"  {memo}", ""])

        lines.append(f"담당의: {self._doctor_name}  {datetime.now().strftime('%Y-%m-%d')}")

        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText("\n".join(lines))
        self._copy_status_lbl.setText("클립보드에 복사되었습니다!")

    # ================================================================
    #  Reset / Load
    # ================================================================

    def reset(self) -> None:
        self._loading = True
        self._recommendations = {"left": None, "right": None}
        self._current_case_id = None
        self._current_report_url = ""
        self._set_read_only(False)
        self._angle_canvas.reset_all()
        self.reload_algorithm_config()
        self._xray_dirty = False

        for side in ("left", "right"):
            p = self._panels[side]
            for lbl in p["angle_displays"].values():
                lbl.setText("-- °")
            self._set_clinical_for_side(side, _default_clinical())
            p["severity_badge"].setText("중증도 미판정")
            p["severity_badge"].setStyleSheet(_SEV_EMPTY_SS)
            p["rec_surgery_lbl"].setText("-")
            p["addon_lbl"].setText("")
            p["agree_radio"].setChecked(True)
            p["override_surgery"].setCurrentIndex(0)
            p["override_reason"].clear()

        self._memo_text.clear()
        self._send_status_lbl.clear()
        self._report_url_lbl.clear()
        self._copy_status_lbl.clear()

        self._auto_load_patient()
        self._loading = False
        self._clear_dirty()

    def load_case(self, case_id: str) -> None:
        from desktop.core import api_client
        try:
            c = api_client.get_case(case_id)
        except api_client.ApiError as e:
            msgbox.warning(self, "케이스 열기 실패", e.message)
            return

        self._loading = True
        self._set_read_only(False)

        # Don't carry the previously open case's recommendation into this one
        self._recommendations = {"left": None, "right": None}
        for p in self._panels.values():
            p["rec_surgery_lbl"].setText("-")
            p["addon_lbl"].setText("")
            p["agree_radio"].setChecked(True)
            p["override_reason"].clear()
        # ...nor its lines/X-ray: a case without saved measurements or image
        # must open empty (reset_all also resets the angle displays via signals)
        self._angle_canvas.reset_all()

        self._selected_patient = {
            "name": c.get("patientName", ""),
            "birth": c.get("patientBirth", ""),
            "phone": c.get("patientPhone", ""),
            "reg_no": c.get("patientRegNo", ""),
        }
        self._pt_name.setText(c.get("patientName", "-"))
        self._pt_birth.setText(c.get("patientBirth", "-"))
        self._pt_phone.setText(c.get("patientPhone", "-"))
        self._pt_reg.setText(c.get("patientRegNo", "-"))
        self._pt_age.setText(str(c.get("patientAge", "-")))

        self._current_case_id = case_id
        self._current_report_url = c.get("reportUrl", "")
        self._report_url_lbl.setText(self._current_report_url)

        angle_data: dict[str, Any] = {}
        raw_json = c.get("angleData") or "{}"
        try:
            angle_data = json.loads(raw_json)
        except (json.JSONDecodeError, TypeError):
            pass

        # foot_side from saved data (always bilateral now)
        _ = angle_data.get("foot_side", "bilateral")

        # X-ray: server first, this PC's cached copy if the server is unreachable
        cache_path = os.path.join(_XRAY_DIR, f"{case_id}.png")
        loaded = False
        if c.get("hasXray"):
            try:
                data = api_client.download_xray(case_id)
                if data and self._angle_canvas.load_image_bytes(data):
                    loaded = True
                    try:
                        os.makedirs(_XRAY_DIR, exist_ok=True)
                        with open(cache_path, "wb") as f:
                            f.write(data)
                    except OSError:
                        pass
            except api_client.ApiError:
                pass
        if not loaded and os.path.exists(cache_path):
            self._angle_canvas.load_image_from_file(cache_path)
        self._xray_dirty = False

        measurements = angle_data.get("measurements", {})
        changed_angles: list[str] = []
        if measurements:
            changed_angles = self._angle_canvas.load_measurements_data(measurements)
            # Show the angles as computed from the restored lines
            for side, prefix in (("left", "L-"), ("right", "R-")):
                p = self._panels[side]
                for base, lbl in p["angle_displays"].items():
                    val = self._angle_canvas.get_angle(prefix + base)
                    lbl.setText(f"{val:.1f}°" if val is not None else "-- °")

        saved_clinical = angle_data.get("clinical", {})
        for side in ("left", "right"):
            self._set_clinical_for_side(side, saved_clinical.get(side, _default_clinical()))

        self._memo_text.setPlainText(c.get("clinicalNotes") or "")

        for side in self._get_active_sides():
            s_data = angle_data.get(f"{side}_surgery", {})
            if s_data.get("algorithm_result"):
                self._recommendations[side] = {
                    "severity": s_data.get("severity"),
                    "surgery": s_data.get("algorithm_result"),
                    "addon_surgery": s_data.get("addon_surgery", ""),
                    "reasons": s_data.get("reasons", []),
                }
                self._update_recommendation_display(side)

            p = self._panels.get(side, {})
            final = s_data.get("final_decision", "")
            algo = s_data.get("algorithm_result", "")
            addon = s_data.get("addon_surgery", "")
            algo_with_addon = f"{algo} + {addon}" if addon else algo
            if final and final != algo and final != algo_with_addon and p:
                p["disagree_radio"].setChecked(True)
                combo = p["override_surgery"]
                name = final.split(" + ")[0]
                idx = combo.findText(name)
                if idx < 0:
                    combo.addItem(name)
                    idx = combo.findText(name)
                combo.setCurrentIndex(idx)
                if s_data.get("override_reason"):
                    p["override_reason"].setText(s_data["override_reason"])

        for side in ("left", "right"):
            if self._recommendations.get(side) is None:
                self._update_realtime_severity(side)

        self._loading = False
        self._clear_dirty()

        me = api_client.current_doctor() or {}
        if c.get("doctorId") != me.get("id"):
            self._set_read_only(True, c.get("doctorName", ""))
            return

        if changed_angles:
            # Saved before the M1 axis was shared: angles now come from one axis
            self._mark_dirty()
            names = ", ".join(sorted(changed_angles))
            msgbox.information(
                self, "측정값 확인 필요",
                "이 케이스는 각도마다 제1중족골 축을 따로 그리던 이전 방식으로 측정되었습니다.\n"
                "HVA의 제1중족골 축을 기준으로 통일해 다시 계산했으며, 아래 각도가 달라졌습니다.\n\n"
                f"{names}\n\n선을 확인하고 필요하면 조정한 뒤 저장하세요.",
            )
