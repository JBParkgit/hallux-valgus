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

from desktop.ui.angle_canvas import AngleCanvas
from desktop.ui import msgbox

_XRAY_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "xray_images")


def _section_title(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setFont(QFont("맑은 고딕", 11, QFont.Weight.Bold))
    lbl.setStyleSheet(
        "color: #111; padding: 2px 0; margin-top: 4px;"
    )
    return lbl


def _separator() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet("color: #ddd; background-color: #ddd;")
    line.setFixedHeight(1)
    return line


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
        "HVA": QColor("#e74c3c"),
        "IMA": QColor("#3498db"),
        "DMAA": QColor("#27ae60"),
    }
    _BI_TYPES: dict[str, QColor] = {
        "L-HVA": QColor("#e74c3c"),
        "L-IMA": QColor("#3498db"),
        "L-DMAA": QColor("#27ae60"),
        "R-HVA": QColor("#c0392b"),
        "R-IMA": QColor("#2980b9"),
        "R-DMAA": QColor("#229954"),
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
        # Track which measurement types have been measured (for X badge)
        self._measured_types: set[str] = set()
        self._dirty: bool = False

        self._init_ui()
        self._connect_dirty_signals()
        self._loading = True
        self._auto_load_patient()
        self._loading = False

    def _mark_dirty(self) -> None:
        if getattr(self, "_loading", False):
            return
        self._dirty = True
        self._dirty_label.setText("[변경사항 있음]")

    def _clear_dirty(self) -> None:
        self._dirty = False
        self._dirty_label.setText("")

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
        outer.setContentsMargins(8, 4, 8, 4)
        outer.setSpacing(6)

        self._build_patient_bar(outer)

        columns = QHBoxLayout()
        columns.setSpacing(6)

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

        # Always bilateral: configure canvas and show both panels
        types = self._BI_TYPES
        self._angle_canvas.set_measurement_types(types)
        self._angle_canvas.active_type = "L-HVA"
        self._panels["left"]["mode_btns"]["HVA"].setChecked(True)

    # ── Patient bar ──────────────────────────────────────────────

    def _build_patient_bar(self, parent_layout: QVBoxLayout) -> None:
        bar = QWidget()
        bar.setStyleSheet("background-color: transparent;")
        ly = QHBoxLayout(bar)
        ly.setContentsMargins(8, 4, 8, 4)
        ly.setSpacing(10)

        _edit_style = (
            "font-weight: bold; color: #2c3e50; border: none; "
            "border-bottom: 1px solid #ccc; background: transparent; padding: 1px 2px;"
        )
        _edit_fields = [
            ("이름:", "_pt_name", 80),
            ("생년월일:", "_pt_birth", 90),
            ("전화:", "_pt_phone", 110),
            ("등록번호:", "_pt_reg", 90),
        ]
        for label_text, attr, width in _edit_fields:
            lbl_w = QLabel(label_text)
            lbl_w.setStyleSheet("color: #7f8c8d; font-size: 11px;")
            ly.addWidget(lbl_w)
            edit = QLineEdit("-")
            edit.setFixedWidth(width)
            edit.setStyleSheet(_edit_style)
            if attr == "_pt_name":
                edit.setFont(QFont("맑은 고딕", 12, QFont.Weight.Bold))
            setattr(self, attr, edit)
            ly.addWidget(edit)
            sep = QLabel("|")
            sep.setStyleSheet("color: #dce1e8;")
            ly.addWidget(sep)

        # Age (read-only, auto-calculated)
        age_lbl_w = QLabel("나이:")
        age_lbl_w.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        ly.addWidget(age_lbl_w)
        self._pt_age = QLabel("-")
        self._pt_age.setStyleSheet("font-weight: bold; color: #2c3e50;")
        ly.addWidget(self._pt_age)
        ly.addWidget(QLabel("세"))

        self._dirty_label = QLabel("")
        self._dirty_label.setStyleSheet("color: #e74c3c; font-size: 11px; font-weight: bold;")
        ly.addWidget(self._dirty_label)

        # Recalculate age when birth changes
        self._pt_birth.textChanged.connect(self._on_birth_changed)

        ly.addStretch()

        reload_btn = QPushButton("환자 불러오기")
        reload_btn.setStyleSheet(
            "padding: 4px 8px; font-size: 11px; background-color: #ecf0f1; "
            "color: #2c3e50; border-radius: 4px;"
        )
        reload_btn.clicked.connect(self._auto_load_patient)
        ly.addWidget(reload_btn)

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
        """Build vertical overlay mode buttons on top of the canvas."""
        p = self._panels[side]
        p["mode_btns"] = {}
        p["clear_btns"] = {}
        _BTN_W = 52

        col = QWidget(self._angle_canvas)
        col.setStyleSheet("background: transparent;")
        col_ly = QVBoxLayout(col)
        col_ly.setContentsMargins(4, 4, 4, 0)
        col_ly.setSpacing(2)

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
                background-color: rgba(150,150,150,0.8); color: white;
                font-weight: bold; font-size: 10px;
                border-radius: {_CLR // 2}px; border: none;
                padding: 0; margin: 0;
                min-height: {_CLR}px; max-height: {_CLR}px;
                min-width: {_CLR}px; max-width: {_CLR}px;
            }}
            QPushButton:hover {{ background-color: rgba(80,80,80,0.9); }}
        """
        for base in ("HVA", "IMA", "DMAA"):
            row = QHBoxLayout()
            row.setSpacing(3)

            btn = QPushButton(base)
            btn.setCheckable(True)
            btn.setFixedWidth(_BTN_W)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: rgba(50,50,50,0.75); color: white;
                    font-weight: bold; padding: 4px 0;
                    border-radius: 4px; border: 2px solid transparent;
                    font-size: 11px;
                }
                QPushButton:checked {
                    border: 2px solid #fff;
                    background-color: rgba(0,0,0,0.85);
                }
            """)
            btn.clicked.connect(lambda checked, s=side, b=base: self._set_angle_mode_for_side(s, b))
            row.addWidget(btn)
            p["mode_btns"][base] = btn

            clear_btn = QPushButton("x")
            clear_btn.setFixedSize(_CLR, _CLR)
            clear_btn.setStyleSheet(_CLR_HIDDEN_SS)
            clear_btn.setEnabled(False)
            clear_btn.clicked.connect(lambda checked, s=side, b=base: self._clear_measurement(s, b))
            clear_btn._ss_visible = _CLR_VISIBLE_SS  # type: ignore[attr-defined]
            clear_btn._ss_hidden = _CLR_HIDDEN_SS  # type: ignore[attr-defined]
            row.addWidget(clear_btn)
            p["clear_btns"][base] = clear_btn

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

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setMinimumWidth(240)
        scroll.setMaximumWidth(340)

        widget = QWidget()
        widget.setStyleSheet("background-color: transparent;")
        ly = QVBoxLayout(widget)
        ly.setContentsMargins(6, 4, 6, 4)
        ly.setSpacing(4)

        side_title = QLabel(f"{side_kr} 발")
        side_title.setFont(QFont("맑은 고딕", 12, QFont.Weight.Bold))
        side_title.setStyleSheet("color: #111; padding: 2px 0 4px 0;")
        ly.addWidget(side_title)

        # ── 1. 임상 소견 ───────────────────────────────────────────
        hyper_cb = QCheckBox("제1중족골 과운동성")
        ly.addWidget(hyper_cb)
        p["hypermobility_cb"] = hyper_cb

        cong_lbl = QLabel("관절 일치성:")
        cong_lbl.setStyleSheet("color: #444; font-size: 11px;")
        ly.addWidget(cong_lbl)
        cong_row = QHBoxLayout()
        cong_r = QRadioButton("Congruent")
        incong_r = QRadioButton("Incongruent")
        cong_r.setChecked(True)
        cong_group = QButtonGroup(self)
        cong_group.addButton(cong_r)
        cong_group.addButton(incong_r)
        cong_row.addWidget(cong_r)
        cong_row.addWidget(incong_r)
        cong_row.addStretch()
        ly.addLayout(cong_row)
        p["congruent_radio"] = cong_r
        p["incongruent_radio"] = incong_r

        oa_lbl = QLabel("골관절염:")
        oa_lbl.setStyleSheet("color: #444; font-size: 11px;")
        ly.addWidget(oa_lbl)
        oa_combo = QComboBox()
        oa_combo.addItems(["None", "Mild", "Moderate", "Severe"])
        ly.addWidget(oa_combo)
        p["oa_grade"] = oa_combo

        ly.addWidget(_separator())

        # ── 2. 측정 각도 ────────────────────────────────────────
        ly.addWidget(_section_title("측정 각도"))
        p["angle_displays"] = {}
        hints = {"HVA": "정상<15°", "IMA": "정상<9°", "DMAA": "정상<10°"}
        for base in ("HVA", "IMA", "DMAA"):
            arow = QHBoxLayout()
            nlbl = QLabel(f"{base}:")
            nlbl.setFont(QFont("맑은 고딕", 10, QFont.Weight.Bold))
            nlbl.setStyleSheet("color: #333;")
            nlbl.setFixedWidth(50)
            arow.addWidget(nlbl)
            vlbl = QLabel("-- °")
            vlbl.setFont(QFont("맑은 고딕", 14, QFont.Weight.Bold))
            vlbl.setStyleSheet("color: #111;")
            arow.addWidget(vlbl)
            p["angle_displays"][base] = vlbl
            hlbl = QLabel(hints[base])
            hlbl.setStyleSheet("color: #999; font-size: 9px;")
            arow.addWidget(hlbl)
            arow.addStretch()
            ly.addLayout(arow)

        sev_badge = QLabel("중증도")
        sev_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sev_badge.setFont(QFont("맑은 고딕", 10, QFont.Weight.Bold))
        sev_badge.setStyleSheet("color: #999; padding: 2px 0;")
        ly.addWidget(sev_badge)
        p["severity_badge"] = sev_badge

        ly.addWidget(_separator())

        # ── 3. 수술 추천 ────────────────────────────────────────
        calc_btn = QPushButton("수술 추천")
        calc_btn.setStyleSheet(
            "padding: 6px; background-color: #222; color: white; "
            "font-weight: bold; border-radius: 4px; font-size: 11px; border: none;"
        )
        calc_btn.clicked.connect(lambda checked=False, s=side: self._run_algorithm(s))
        ly.addWidget(calc_btn)
        p["calc_btn"] = calc_btn

        rec_lbl = QLabel("-")
        rec_lbl.setFont(QFont("맑은 고딕", 13, QFont.Weight.Bold))
        rec_lbl.setStyleSheet("color: #111; padding: 2px 0;")
        rec_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        rec_lbl.setWordWrap(True)
        ly.addWidget(rec_lbl)
        p["rec_surgery_lbl"] = rec_lbl

        addon_lbl = QLabel("")
        addon_lbl.setFont(QFont("맑은 고딕", 13, QFont.Weight.Bold))
        addon_lbl.setStyleSheet("color: #111; padding: 2px 0;")
        addon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ly.addWidget(addon_lbl)
        p["addon_lbl"] = addon_lbl

        ly.addWidget(_separator())

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
        override_reason.setPlaceholderText("변경 사유")
        override_reason.setEnabled(False)
        override_reason.setMaximumHeight(60)
        ly.addWidget(override_reason)
        p["override_reason"] = override_reason

        disagree_radio.toggled.connect(override_surgery.setEnabled)
        disagree_radio.toggled.connect(override_reason.setEnabled)

        ly.addStretch()

        scroll.setWidget(widget)
        p["container"] = scroll

        self._panels[side] = p
        parent_layout.addWidget(scroll)

    # ── Bottom bar ───────────────────────────────────────────────

    def _build_bottom_bar(self, parent_layout: QVBoxLayout) -> None:
        bar = QWidget()
        bar.setStyleSheet("background-color: transparent;")
        bar_ly = QVBoxLayout(bar)
        bar_ly.setContentsMargins(8, 4, 8, 4)
        bar_ly.setSpacing(4)

        memo_row = QHBoxLayout()
        memo_lbl = QLabel("메모:")
        memo_lbl.setStyleSheet("color: #555;")
        memo_row.addWidget(memo_lbl)
        self._memo_text = QTextEdit()
        self._memo_text.setMaximumHeight(45)
        self._memo_text.setPlaceholderText("추가 참고 사항...")
        memo_row.addWidget(self._memo_text)
        bar_ly.addLayout(memo_row)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        _S = (
            "padding: 5px 12px; color: white; font-weight: bold; "
            "border-radius: 3px; font-size: 11px; border: none;"
        )
        for label, bg, handler in [
            ("저장", "#333", self._save_only),
            ("알림톡 발송", "#555", self._save_and_send),
            ("EMR 복사", "#444", self._copy_to_emr),
        ]:
            btn = QPushButton(label)
            btn.setStyleSheet(f"background-color: {bg}; {_S}")
            btn.clicked.connect(handler)
            btn_row.addWidget(btn)

        btn_row.addStretch()
        self._send_status_lbl = QLabel("")
        self._send_status_lbl.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        btn_row.addWidget(self._send_status_lbl)
        bar_ly.addLayout(btn_row)

        status_row = QHBoxLayout()
        self._report_url_lbl = QLabel("")
        self._report_url_lbl.setVisible(False)
        self._copy_status_lbl = QLabel("")
        self._copy_status_lbl.setStyleSheet("color: #333; font-size: 10px;")
        status_row.addWidget(self._copy_status_lbl)
        status_row.addStretch()
        bar_ly.addLayout(status_row)

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
        self._pt_name.setText("(SMS_Patient.txt 없음)")
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

    def _set_angle_mode_for_side(self, side: str, base: str) -> None:
        """Set canvas active measurement type from a side panel button click."""
        name = self._measurement_name(side, base)
        self._angle_canvas.active_type = name

        # Update checked state on both panels
        for s in ("left", "right"):
            for b, btn in self._panels[s]["mode_btns"].items():
                expected = self._measurement_name(s, b)
                btn.setChecked(expected == name)

    def _sync_mode_btn_checked(self, side: str, active_base: str | None) -> None:
        """Set checked state for a panel's mode buttons."""
        for base, btn in self._panels[side]["mode_btns"].items():
            btn.setChecked(base == active_base)

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

    def _clear_measurement(self, side: str, base: str) -> None:
        """Clear a specific measurement when X badge is clicked."""
        name = self._measurement_name(side, base)
        self._angle_canvas.reset_measurement(name)
        self._measured_types.discard(name)
        p = self._panels[side]
        if base in p["angle_displays"]:
            p["angle_displays"][base].setText("-- °")
        self._show_clear_btn(p["clear_btns"][base], False)
        self._update_realtime_severity(side)

    def _update_clear_badge(self, side: str, base: str) -> None:
        """Show/hide X badge based on whether measurement exists."""
        name = self._measurement_name(side, base)
        has_angle = self._angle_canvas.get_angle(name) is not None
        self._show_clear_btn(self._panels[side]["clear_btns"][base], has_angle)

    def _refresh_all_clear_badges(self) -> None:
        """Refresh all X badges for current foot mode."""
        for side in ("left", "right"):
            if not self._panels[side]["container"].isVisible():
                for base in ("HVA", "IMA", "DMAA"):
                    self._show_clear_btn(self._panels[side]["clear_btns"][base], False)
                continue
            for base in ("HVA", "IMA", "DMAA"):
                self._update_clear_badge(side, base)

    _ANGLE_ORDER = ("HVA", "IMA", "DMAA")

    def _on_angle_measured(self, name: str, angle: float) -> None:
        self._mark_dirty()
        self._measured_types.add(name)
        side, base = self._resolve_side_and_base(name)
        if side and base:
            p = self._panels.get(side)
            if p and base in p["angle_displays"]:
                p["angle_displays"][base].setText(f"{angle:.1f}°")
                self._show_clear_btn(p["clear_btns"][base], True)
            # Auto-advance to next unmeasured angle on the SAME side
            self._auto_advance(side, base)
            self._update_realtime_severity(side)

    def _on_angle_reset(self, name: str) -> None:
        self._measured_types.discard(name)
        side, base = self._resolve_side_and_base(name)
        if side and base:
            p = self._panels.get(side)
            if p and base in p["angle_displays"]:
                p["angle_displays"][base].setText("-- °")
                self._show_clear_btn(p["clear_btns"][base], False)
            self._update_realtime_severity(side)

    def _update_realtime_severity(self, side: str) -> None:
        """Update severity badge when all 3 angles are measured."""
        p = self._panels.get(side)
        if not p:
            return
        angles = self._get_angles_for_side(side)
        hva = angles.get("hva")
        ima = angles.get("ima")
        dmaa = angles.get("dmaa")
        if hva is None or ima is None or dmaa is None:
            p["severity_badge"].setText("중증도")
            p["severity_badge"].setStyleSheet("color: #999; padding: 2px 0;")
            return
        # Classify severity by HVA
        if hva < 20:
            sev_kr = "경증"
        elif hva < 40:
            sev_kr = "중등도"
        else:
            sev_kr = "중증"
        sev_colors = {"경증": "#888", "중등도": "#555", "중증": "#222"}
        color = sev_colors.get(sev_kr, "#999")
        p["severity_badge"].setText(sev_kr)
        p["severity_badge"].setStyleSheet(
            f"color: {color}; padding: 2px 0; font-weight: bold;"
        )

    def _auto_advance(self, side: str, completed_base: str) -> None:
        """Advance to next unmeasured angle on the same side only."""
        idx = self._ANGLE_ORDER.index(completed_base) if completed_base in self._ANGLE_ORDER else -1
        for i in range(1, len(self._ANGLE_ORDER)):
            next_base = self._ANGLE_ORDER[(idx + i) % len(self._ANGLE_ORDER)]
            next_name = self._measurement_name(side, next_base)
            if next_name not in self._measured_types:
                self._set_angle_mode_for_side(side, next_base)
                return
        # All measured on this side — stay on current, don't cross to other side

    def _paste_xray(self) -> None:
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
        try:
            from desktop.core.algorithm_config import load_config
            if self._doctor_id:
                self._algorithm_config = load_config(self._doctor_id)
        except Exception:
            self._algorithm_config = None

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
        hva = angles.get("hva") or 0.0
        ima = angles.get("ima") or 0.0

        if hva == 0 and ima == 0:
            msgbox.warning(self, "각도 미측정", "HVA, IMA 각도를 먼저 측정해 주세요.")
            return

        clinical = self._get_clinical_for_side(side)

        try:
            from desktop.core.algorithm import recommend_surgery

            if self._algorithm_config is None:
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
        sev_colors = {"경증": "#888", "중등도": "#555", "중증": "#222"}
        color = sev_colors.get(sev_kr, "#999")

        p["severity_badge"].setText(sev_kr)
        p["severity_badge"].setStyleSheet(
            f"color: {color}; padding: 2px 0; font-weight: bold;"
        )
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
            "doctorId": self._doctor_id,
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

        try:
            from desktop.core.database import create_case, update_case, get_case
            if self._current_case_id:
                update_case(self._current_case_id, case_record)
                case_id = self._current_case_id
            else:
                case_id = create_case(case_record)
                self._current_case_id = case_id
            self._clear_dirty()

            os.makedirs(_XRAY_DIR, exist_ok=True)
            img_path = os.path.join(_XRAY_DIR, f"{case_id}.png")
            self._angle_canvas.save_image_to_file(img_path)

            saved = get_case(case_id)
            report_hash = saved.get("reportHash", "") if saved else ""
            self._current_report_url = f"https://hallux-valgus.vercel.app/report/{report_hash}"
            self._report_url_lbl.setText(self._current_report_url)
            return case_id
        except ImportError:
            self._clear_dirty()
            self._current_report_url = "https://example.com/report/demo"
            self._report_url_lbl.setText(self._current_report_url)
            return "demo-id"
        except Exception as e:
            msgbox.critical(self, "저장 실패", f"DB 저장 오류:\n{e}")
            return None

    def _save_only(self) -> None:
        case_id = self._save_case()
        if case_id:
            self._send_status_lbl.setText("저장 완료!")
            self._send_status_lbl.setStyleSheet("color: #333; font-size: 11px; font-weight: bold;")
            self.case_saved.emit()
            msgbox.information(self, "저장 완료", "케이스가 성공적으로 저장되었습니다.")

    def _save_and_send(self) -> None:
        case_id = self._save_case()
        if case_id:
            self._send_status_lbl.setText("저장 완료. 알림톡 발송 중...")
            self._send_status_lbl.setStyleSheet("color: #666; font-size: 11px;")
            QApplication.processEvents()
            self._send_alimtalk()
            self.case_saved.emit()

    def _send_alimtalk(self) -> None:
        patient = self._get_patient_from_fields()
        if not patient:
            msgbox.warning(self, "발송 실패", "환자 정보가 없습니다.")
            return
        phone = patient.get("phone", "")
        if not phone or phone == "-":
            msgbox.warning(self, "발송 실패", "환자 전화번호가 없습니다.")
            return
        if not self._current_report_url:
            if not self._save_case():
                return

        self._send_status_lbl.setText("발송 중...")
        self._send_status_lbl.setStyleSheet("color: #666; font-size: 11px;")
        QApplication.processEvents()

        try:
            from desktop.core.alimtalk import build_report_button, send_alimtalk
            patient_name = patient.get("name", "")
            message = (
                f"[달려라병원] {patient_name}님의 무지외반증 수술 안내서가 준비되었습니다.\n"
                f"아래 버튼을 눌러 확인해 주세요."
            )
            buttons = [build_report_button(self._current_report_url)]
            result = send_alimtalk(
                phone=phone, template_code="hallux_report",
                message=message, buttons=buttons,
            )
            if result.get("success"):
                self._send_status_lbl.setText("알림톡 발송 완료!")
                self._send_status_lbl.setStyleSheet("color: #333; font-size: 11px; font-weight: bold;")
                try:
                    from desktop.core.database import update_case
                    if self._current_case_id:
                        update_case(self._current_case_id, {
                            "alimtalkSent": True, "alimtalkSentAt": datetime.now(),
                        })
                except Exception:
                    pass
            else:
                self._send_status_lbl.setText(f"발송 실패: {result.get('error', '오류')}")
                self._send_status_lbl.setStyleSheet("color: #333; font-size: 11px;")
        except ImportError:
            self._send_status_lbl.setText("알림톡 발송 완료 (데모)")
            self._send_status_lbl.setStyleSheet("color: #333; font-size: 11px;")

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
        self._measured_types.clear()
        self._angle_canvas.reset_all()

        for side in ("left", "right"):
            p = self._panels[side]
            for lbl in p["angle_displays"].values():
                lbl.setText("-- °")
            for btn in p["clear_btns"].values():
                self._show_clear_btn(btn, False)
            self._set_clinical_for_side(side, _default_clinical())
            p["severity_badge"].setText("중증도")
            p["severity_badge"].setStyleSheet("color: #999; padding: 2px 0;")
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
        try:
            from desktop.core.database import get_case
            c = get_case(case_id)
        except Exception:
            c = None
        if not c:
            return

        self._loading = True

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
        report_hash = c.get("reportHash", "")
        self._current_report_url = f"https://hallux-valgus.vercel.app/report/{report_hash}"
        self._report_url_lbl.setText(self._current_report_url)

        angle_data: dict[str, Any] = {}
        raw_json = c.get("angleData") or "{}"
        try:
            angle_data = json.loads(raw_json)
        except (json.JSONDecodeError, TypeError):
            pass

        # foot_side from saved data (always bilateral now)
        _ = angle_data.get("foot_side", "bilateral")

        img_path = c.get("xrayImageUrl") or os.path.join(_XRAY_DIR, f"{case_id}.png")
        if os.path.exists(img_path):
            self._angle_canvas.load_image_from_file(img_path)

        measurements = angle_data.get("measurements", {})
        if measurements:
            self._angle_canvas.load_measurements_data(measurements)
            for meas_name, m_data in measurements.items():
                angle_val = m_data.get("angle")
                side, base = self._resolve_side_and_base(meas_name)
                if side and base and angle_val is not None:
                    p = self._panels.get(side)
                    if p and base in p["angle_displays"]:
                        p["angle_displays"][base].setText(f"{angle_val:.1f}°")
                        self._show_clear_btn(p["clear_btns"][base], True)
                        self._measured_types.add(meas_name)

        saved_clinical = angle_data.get("clinical", {})
        for side in ("left", "right"):
            if side in saved_clinical:
                self._set_clinical_for_side(side, saved_clinical[side])

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
                idx = combo.findText(final.split(" + ")[0])
                if idx >= 0:
                    combo.setCurrentIndex(idx)
                if s_data.get("override_reason"):
                    p["override_reason"].setText(s_data["override_reason"])

        self._loading = False
        self._clear_dirty()
