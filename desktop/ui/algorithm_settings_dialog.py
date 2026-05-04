"""의사별 수술 추천 알고리즘 설정 다이얼로그."""

from __future__ import annotations

from typing import Any

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from desktop.core.algorithm_config import DEFAULT_SURGERIES, default_config, load_config, save_config
from desktop.ui import msgbox


class AlgorithmSettingsDialog(QDialog):
    """의사별 알고리즘 설정 편집 다이얼로그."""

    def __init__(self, doctor_id: str, doctor_name: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._doctor_id = doctor_id
        self._doctor_name = doctor_name
        self._config = load_config(doctor_id)
        self._init_ui()
        self._load_values()

    def _init_ui(self) -> None:
        self.setWindowTitle(f"알고리즘 설정 - {self._doctor_name}")
        self.setMinimumSize(580, 680)

        outer = QVBoxLayout(self)
        outer.setSpacing(12)
        outer.setContentsMargins(16, 16, 16, 16)

        # Header
        header = QLabel(f"{self._doctor_name} 선생님의 수술 추천 알고리즘 설정")
        header.setFont(QFont("맑은 고딕", 13, QFont.Weight.Bold))
        header.setStyleSheet("color: #2c3e50;")
        outer.addWidget(header)

        desc = QLabel("아래 값들을 수정하여 환자별 수술 추천 기준을 조정할 수 있습니다.")
        desc.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        desc.setWordWrap(True)
        outer.addWidget(desc)

        # Scrollable content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        content = QWidget()
        self._form_layout = QVBoxLayout(content)
        self._form_layout.setSpacing(12)

        self._build_surgery_management_section()
        self._build_severity_section()
        self._build_surgery_map_section()
        self._build_dmaa_section()
        self._build_age_section()

        self._form_layout.addStretch()
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        reset_btn = QPushButton("기본값으로 초기화")
        reset_btn.setStyleSheet(
            "padding: 8px 16px; background-color: #e74c3c; color: white; "
            "border-radius: 6px; font-weight: bold;"
        )
        reset_btn.clicked.connect(self._reset_to_default)
        btn_row.addWidget(reset_btn)

        save_btn = QPushButton("저장")
        save_btn.setStyleSheet(
            "padding: 8px 24px; background-color: #27ae60; color: white; "
            "border-radius: 6px; font-weight: bold; font-size: 13px;"
        )
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        cancel_btn = QPushButton("취소")
        cancel_btn.setStyleSheet(
            "padding: 8px 16px; background-color: #95a5a6; color: white; "
            "border-radius: 6px;"
        )
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        outer.addLayout(btn_row)

    # ── Surgery list helpers ────────────────────────────────────

    def _get_surgery_list(self) -> list[str]:
        """Return current surgery names from the management table."""
        names: list[str] = []
        for row in range(self._surgery_table.rowCount()):
            item = self._surgery_table.item(row, 0)
            if item:
                t = item.text().strip()
                if t:
                    names.append(t)
        return names

    def _refresh_surgery_combos(self) -> None:
        """Refresh all surgery combo boxes with the current surgery list."""
        if not hasattr(self, "_surgery_combos"):
            return
        surgeries = self._get_surgery_list()
        for combo in self._surgery_combos.values():
            current = combo.currentText()
            combo.clear()
            combo.addItems(surgeries)
            idx = combo.findText(current)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setEditText(current)
        current_dmaa = self._dmaa_surgery.currentText()
        self._dmaa_surgery.clear()
        self._dmaa_surgery.addItems(surgeries)
        idx = self._dmaa_surgery.findText(current_dmaa)
        if idx >= 0:
            self._dmaa_surgery.setCurrentIndex(idx)
        else:
            self._dmaa_surgery.setEditText(current_dmaa)

    # ── Surgery Management Section ───────────────────────────────

    def _build_surgery_management_section(self) -> None:
        group = QGroupBox("수술명 관리")
        group.setFont(QFont("맑은 고딕", 11, QFont.Weight.Bold))
        ly = QVBoxLayout(group)

        info = QLabel("수술명을 추가, 수정, 삭제할 수 있습니다. 여기서 관리하는 수술명이 아래 매핑에 사용됩니다.")
        info.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        info.setWordWrap(True)
        ly.addWidget(info)

        self._surgery_table = QTableWidget(0, 1)
        self._surgery_table.setHorizontalHeaderLabels(["수술명"])
        self._surgery_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._surgery_table.setMinimumHeight(140)
        self._surgery_table.verticalHeader().setVisible(False)
        self._surgery_table.cellChanged.connect(lambda: self._refresh_surgery_combos())
        ly.addWidget(self._surgery_table)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("+ 수술 추가")
        add_btn.setStyleSheet(
            "padding: 4px 12px; background-color: #3498db; color: white; "
            "border-radius: 4px; font-size: 11px;"
        )
        add_btn.clicked.connect(self._add_surgery_row)
        btn_row.addWidget(add_btn)

        del_btn = QPushButton("- 선택 삭제")
        del_btn.setStyleSheet(
            "padding: 4px 12px; background-color: #e74c3c; color: white; "
            "border-radius: 4px; font-size: 11px;"
        )
        del_btn.clicked.connect(self._delete_surgery_row)
        btn_row.addWidget(del_btn)

        reset_btn = QPushButton("기본 수술 복원")
        reset_btn.setStyleSheet(
            "padding: 4px 12px; background-color: #95a5a6; color: white; "
            "border-radius: 4px; font-size: 11px;"
        )
        reset_btn.clicked.connect(self._reset_surgery_list)
        btn_row.addWidget(reset_btn)

        btn_row.addStretch()
        ly.addLayout(btn_row)

        self._form_layout.addWidget(group)

    def _add_surgery_row(self) -> None:
        row = self._surgery_table.rowCount()
        self._surgery_table.insertRow(row)
        self._surgery_table.setItem(row, 0, QTableWidgetItem(""))
        self._surgery_table.editItem(self._surgery_table.item(row, 0))

    def _delete_surgery_row(self) -> None:
        row = self._surgery_table.currentRow()
        if row < 0:
            return
        item = self._surgery_table.item(row, 0)
        name = item.text().strip() if item else ""
        # Check if this surgery is used in mappings
        used_in: list[str] = []
        for key, combo in self._surgery_combos.items():
            if combo.currentText() == name:
                used_in.append(key)
        if self._dmaa_surgery.currentText() == name:
            used_in.append("DMAA 보조 수술")
        if used_in:
            msgbox.warning(
                self, "삭제 불가",
                f"'{name}'은(는) 수술 매핑에서 사용 중입니다.\n"
                f"사용처: {', '.join(used_in)}\n"
                "매핑을 먼저 변경해 주세요.",
            )
            return
        self._surgery_table.removeRow(row)
        self._refresh_surgery_combos()

    def _reset_surgery_list(self) -> None:
        reply = msgbox.question(
            self, "수술 목록 초기화",
            "수술 목록을 기본값으로 되돌리시겠습니까?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._surgery_table.setRowCount(0)
        for name in DEFAULT_SURGERIES:
            row = self._surgery_table.rowCount()
            self._surgery_table.insertRow(row)
            self._surgery_table.setItem(row, 0, QTableWidgetItem(name))
        self._refresh_surgery_combos()

    # ── Severity Section ─────────────────────────────────────────

    def _build_severity_section(self) -> None:
        group = QGroupBox("중증도 분류 기준")
        group.setFont(QFont("맑은 고딕", 11, QFont.Weight.Bold))
        form = QFormLayout(group)
        form.setSpacing(8)

        info = QLabel(
            "경증: HVA < 중등도HVA AND IMA < 중등도IMA\n"
            "중등도: HVA ≥ 중등도HVA OR IMA ≥ 중등도IMA\n"
            "중증: HVA > 중증HVA OR IMA > 중증IMA"
        )
        info.setStyleSheet("color: #7f8c8d; font-size: 11px; padding: 4px;")
        form.addRow(info)

        self._moderate_hva = QDoubleSpinBox()
        self._moderate_hva.setRange(10, 60)
        self._moderate_hva.setSuffix("°")
        self._moderate_hva.setDecimals(1)
        form.addRow("중등도 HVA 기준 (≥):", self._moderate_hva)

        self._moderate_ima = QDoubleSpinBox()
        self._moderate_ima.setRange(5, 30)
        self._moderate_ima.setSuffix("°")
        self._moderate_ima.setDecimals(1)
        form.addRow("중등도 IMA 기준 (≥):", self._moderate_ima)

        self._severe_hva = QDoubleSpinBox()
        self._severe_hva.setRange(20, 80)
        self._severe_hva.setSuffix("°")
        self._severe_hva.setDecimals(1)
        form.addRow("중증 HVA 기준 (>):", self._severe_hva)

        self._severe_ima = QDoubleSpinBox()
        self._severe_ima.setRange(10, 40)
        self._severe_ima.setSuffix("°")
        self._severe_ima.setDecimals(1)
        form.addRow("중증 IMA 기준 (>):", self._severe_ima)

        self._form_layout.addWidget(group)

    # ── Surgery Map Section ──────────────────────────────────────

    def _build_surgery_map_section(self) -> None:
        group = QGroupBox("중증도별 수술 매핑")
        group.setFont(QFont("맑은 고딕", 11, QFont.Weight.Bold))
        form = QFormLayout(group)
        form.setSpacing(8)

        self._surgery_combos: dict[str, QComboBox] = {}
        surgeries = self._get_surgery_list()

        rows = [
            ("mild", "경증 →"),
            ("moderate", "중등도 →"),
            ("severe", "중증 →"),
            ("severe_hypermobility", "중증 + 과운동성 →"),
            ("severe_oa", "심한 골관절염 →"),
        ]

        for key, label in rows:
            combo = QComboBox()
            combo.setEditable(True)
            combo.addItems(surgeries)
            form.addRow(label, combo)
            self._surgery_combos[key] = combo

        self._form_layout.addWidget(group)

    # ── DMAA Section ─────────────────────────────────────────────

    def _build_dmaa_section(self) -> None:
        group = QGroupBox("DMAA 보조 수술 기준")
        group.setFont(QFont("맑은 고딕", 11, QFont.Weight.Bold))
        form = QFormLayout(group)

        self._dmaa_threshold = QDoubleSpinBox()
        self._dmaa_threshold.setRange(0, 30)
        self._dmaa_threshold.setSuffix("°")
        self._dmaa_threshold.setDecimals(1)
        form.addRow("DMAA 기준값 (초과 시 추가 수술):", self._dmaa_threshold)

        self._dmaa_surgery = QComboBox()
        self._dmaa_surgery.setEditable(True)
        self._dmaa_surgery.addItems(self._get_surgery_list())
        form.addRow("추가 수술:", self._dmaa_surgery)

        self._form_layout.addWidget(group)

    # ── Age Section ──────────────────────────────────────────────

    def _build_age_section(self) -> None:
        group = QGroupBox("고령 환자 경고")
        group.setFont(QFont("맑은 고딕", 11, QFont.Weight.Bold))
        form = QFormLayout(group)

        self._age_warning = QSpinBox()
        self._age_warning.setRange(40, 100)
        self._age_warning.setSuffix("세 이상")
        form.addRow("고령 경고 기준:", self._age_warning)

        self._form_layout.addWidget(group)

    # ── Load / Save ──────────────────────────────────────────────

    def _load_values(self) -> None:
        """Load config values into UI widgets."""
        cfg = self._config

        # Surgery list
        surgeries = cfg.get("surgeries", list(DEFAULT_SURGERIES))
        self._surgery_table.setRowCount(0)
        for name in surgeries:
            row = self._surgery_table.rowCount()
            self._surgery_table.insertRow(row)
            self._surgery_table.setItem(row, 0, QTableWidgetItem(name))

        sev = cfg.get("severity", {})

        self._moderate_hva.setValue(sev.get("moderate_hva", 30))
        self._moderate_ima.setValue(sev.get("moderate_ima", 14))
        self._severe_hva.setValue(sev.get("severe_hva", 40))
        self._severe_ima.setValue(sev.get("severe_ima", 16))

        smap = cfg.get("surgery_map", {})
        for key, combo in self._surgery_combos.items():
            val = smap.get(key, "")
            idx = combo.findText(val)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                combo.setEditText(val)

        self._dmaa_threshold.setValue(cfg.get("dmaa_threshold", 10.0))
        dmaa_surg = cfg.get("dmaa_surgery", "Akin 절골술")
        idx = self._dmaa_surgery.findText(dmaa_surg)
        if idx >= 0:
            self._dmaa_surgery.setCurrentIndex(idx)
        else:
            self._dmaa_surgery.setEditText(dmaa_surg)

        self._age_warning.setValue(cfg.get("age_warning", 60))

    def _collect_values(self) -> dict[str, Any]:
        """Collect current UI values into a config dict."""
        cfg: dict[str, Any] = {
            "surgeries": self._get_surgery_list(),
            "severity": {
                "moderate_hva": self._moderate_hva.value(),
                "moderate_ima": self._moderate_ima.value(),
                "severe_hva": self._severe_hva.value(),
                "severe_ima": self._severe_ima.value(),
            },
            "surgery_map": {
                key: combo.currentText()
                for key, combo in self._surgery_combos.items()
            },
            "dmaa_threshold": self._dmaa_threshold.value(),
            "dmaa_surgery": self._dmaa_surgery.currentText(),
            "age_warning": self._age_warning.value(),
        }

        return cfg

    def _save(self) -> None:
        cfg = self._collect_values()

        # Validate
        sev = cfg["severity"]
        if sev["moderate_hva"] >= sev["severe_hva"]:
            msgbox.warning(self, "설정 오류", "중등도 HVA 기준은 중증 HVA 기준보다 작아야 합니다.")
            return
        if sev["moderate_ima"] >= sev["severe_ima"]:
            msgbox.warning(self, "설정 오류", "중등도 IMA 기준은 중증 IMA 기준보다 작아야 합니다.")
            return

        try:
            save_config(self._doctor_id, cfg)
            self._config = cfg
            msgbox.information(self, "저장 완료", "알고리즘 설정이 저장되었습니다.")
            self.accept()
        except Exception as e:
            msgbox.critical(self, "저장 실패", f"설정 저장 중 오류:\n{e}")

    def _reset_to_default(self) -> None:
        reply = msgbox.question(
            self, "초기화",
            "모든 설정을 기본값으로 되돌리시겠습니까?",
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._config = default_config()
            self._load_values()

    def get_config(self) -> dict[str, Any]:
        """Return current config (after dialog closes)."""
        return self._config
