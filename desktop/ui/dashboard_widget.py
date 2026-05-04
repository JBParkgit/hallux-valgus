"""Dashboard widget showing a searchable, sortable list of all cases."""

from __future__ import annotations

import json

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from desktop.ui import msgbox


class DashboardWidget(QWidget):
    """Case list table with search, filter, and action buttons."""

    new_case_requested = pyqtSignal()
    case_selected = pyqtSignal(str)  # case_id (CUID string)
    case_deleted = pyqtSignal()  # emitted after successful deletion

    # Column definitions
    _COLUMNS = ["날짜", "환자명", "생년월일", "등록번호", "중증도", "수술법", ""]
    _SEVERITY_MAP: dict[str, str] = {
        "mild": "경증", "moderate": "중등도", "severe": "중증",
        "경증": "경증", "중등도": "중등도", "중증": "중증",
    }
    _SEVERITY_COLORS: dict[str, str] = {
        "경증": "#27ae60",
        "중등도": "#f39c12",
        "중증": "#e74c3c",
    }

    def __init__(self, doctor_id: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._doctor_id = doctor_id
        self._case_data: list[dict] = []
        self._init_ui()
        self.refresh_data()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # ── Header row ───────────────────────────────────────────
        header_row = QHBoxLayout()

        title = QLabel("📋 케이스 대시보드")
        title.setFont(QFont("맑은 고딕", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #2c3e50;")
        header_row.addWidget(title)

        header_row.addStretch()

        new_case_btn = QPushButton("➕ 새 케이스")
        new_case_btn.setProperty("class", "success")
        new_case_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 24px;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #219a52; }
        """)
        new_case_btn.clicked.connect(self.new_case_requested.emit)
        header_row.addWidget(new_case_btn)

        layout.addLayout(header_row)

        # ── Search bar ───────────────────────────────────────────
        search_row = QHBoxLayout()

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("🔍 환자명, 등록번호로 검색...")
        self._search_input.setMinimumHeight(38)
        self._search_input.setMaximumWidth(400)
        self._search_input.textChanged.connect(self._apply_filter)
        search_row.addWidget(self._search_input)

        search_row.addStretch()

        self._count_label = QLabel("총 0건")
        self._count_label.setStyleSheet("color: #7f8c8d; font-size: 13px;")
        search_row.addWidget(self._count_label)

        layout.addLayout(search_row)

        # ── Table ────────────────────────────────────────────────
        self._table = QTableWidget()
        self._table.setColumnCount(len(self._COLUMNS))
        self._table.setHorizontalHeaderLabels(self._COLUMNS)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet("""
            QTableWidget {
                alternate-background-color: #fafbfc;
            }
        """)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(36)
        self._table.setSortingEnabled(True)
        self._table.doubleClicked.connect(self._on_row_double_clicked)

        # Column stretch
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)  # 날짜
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)  # 환자명
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)  # 생년월일
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)  # 등록번호
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)  # 중증도
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)           # 수술법
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Fixed)             # 삭제
        header.resizeSection(6, 70)

        layout.addWidget(self._table)

    # ── Data ────────────────────────────────────────────────────

    def refresh_data(self) -> None:
        """Reload case list from database."""
        try:
            from desktop.core.database import get_all_cases
            self._case_data = get_all_cases()
        except ImportError:
            # Demo data when core module not available
            self._case_data = self._demo_data()

        self._populate_table(self._case_data)

    def _populate_table(self, data: list[dict]) -> None:
        """Fill the table with given case records."""
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        self._table.setRowCount(len(data))

        for row, case in enumerate(data):
            # 날짜 (DB: createdAt datetime or demo: date string)
            raw_date = case.get("createdAt") or case.get("date", "")
            if hasattr(raw_date, "strftime"):
                date_str = raw_date.strftime("%Y-%m-%d %H:%M")
            else:
                date_str = str(raw_date) if raw_date else ""
            date_item = QTableWidgetItem(date_str)
            date_item.setData(Qt.ItemDataRole.UserRole, case.get("id", row))
            self._table.setItem(row, 0, date_item)

            # 환자명 (DB: patientName)
            name = case.get("patientName") or case.get("patient_name", "")
            self._table.setItem(row, 1, QTableWidgetItem(name))

            # 생년월일 (DB: patientBirth)
            birth = case.get("patientBirth") or case.get("birth_date", "")
            self._table.setItem(row, 2, QTableWidgetItem(str(birth)))

            # 등록번호 (DB: patientRegNo)
            reg_no = case.get("patientRegNo", "")
            self._table.setItem(row, 3, QTableWidgetItem(str(reg_no)))

            # 중증도 (bilateral: 좌/우)
            left_sev_raw, right_sev_raw = self._extract_bilateral(case, "severity")
            left_sev = self._SEVERITY_MAP.get(left_sev_raw, left_sev_raw)
            right_sev = self._SEVERITY_MAP.get(right_sev_raw, right_sev_raw)
            if left_sev and right_sev:
                sev_text = f"{left_sev} / {right_sev}"
            elif left_sev:
                sev_text = left_sev
            elif right_sev:
                sev_text = right_sev
            else:
                fallback = case.get("severity", "")
                sev_text = self._SEVERITY_MAP.get(fallback, fallback)
            sev_item = QTableWidgetItem(sev_text)
            primary_sev = left_sev or right_sev or self._SEVERITY_MAP.get(case.get("severity", ""), "")
            color = self._SEVERITY_COLORS.get(primary_sev, "#7f8c8d")
            sev_item.setForeground(QColor(color))
            sev_item.setFont(QFont("맑은 고딕", 10, QFont.Weight.Bold))
            self._table.setItem(row, 4, sev_item)

            # 수술법 (bilateral: 좌/우)
            left_surg, right_surg = self._extract_bilateral(case, "surgery")
            if left_surg and right_surg:
                surgery_text = f"{left_surg} / {right_surg}"
            elif left_surg:
                surgery_text = left_surg
            elif right_surg:
                surgery_text = right_surg
            else:
                surgery_text = (
                    case.get("finalDecision")
                    or case.get("algorithmResult")
                    or case.get("surgery", "")
                    or ""
                )
            self._table.setItem(row, 5, QTableWidgetItem(surgery_text))

            # 삭제 버튼
            case_id = case.get("id", "")
            del_btn = QPushButton("삭제")
            del_btn.setFixedSize(60, 26)
            del_btn.setStyleSheet(
                "background-color: #e74c3c; color: white; font-size: 11px; "
                "padding: 0px; border-radius: 4px; border: none; "
                "min-height: 0px; max-height: 26px; min-width: 0px;"
            )
            del_btn.clicked.connect(
                lambda checked, cid=str(case_id), nm=name: self._on_delete_clicked(cid, nm)
            )
            self._table.setCellWidget(row, 6, del_btn)

        self._table.setSortingEnabled(True)
        self._count_label.setText(f"총 {len(data)}건")

    # ── Filter ──────────────────────────────────────────────────

    def _apply_filter(self, text: str) -> None:
        """Filter table rows by search text."""
        query = text.strip().lower()
        if not query:
            self._populate_table(self._case_data)
            return

        filtered = [
            c
            for c in self._case_data
            if query in (c.get("patientName") or c.get("patient_name", "")).lower()
            or query in (c.get("finalDecision") or c.get("algorithmResult") or c.get("surgery", "")).lower()
            or query in (c.get("patientRegNo", "")).lower()
        ]
        self._populate_table(filtered)

    # ── Bilateral helpers ───────────────────────────────────────

    @staticmethod
    def _extract_bilateral(case: dict, field: str) -> tuple[str, str]:
        """Extract left/right values from angleData JSON.

        Returns (left_value, right_value). Either may be empty string.
        """
        raw = case.get("angleData") or "{}"
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            return ("", "")

        left_data = data.get("left_surgery", {})
        right_data = data.get("right_surgery", {})

        if field == "severity":
            return (left_data.get("severity") or "", right_data.get("severity") or "")
        elif field == "surgery":
            l = left_data.get("final_decision") or left_data.get("algorithm_result") or ""
            r = right_data.get("final_decision") or right_data.get("algorithm_result") or ""
            return (l, r)
        return ("", "")

    # ── Delete ───────────────────────────────────────────────────

    def _on_delete_clicked(self, case_id: str, patient_name: str) -> None:
        """Confirm and delete a case."""
        reply = msgbox.question(
            self,
            "케이스 삭제",
            f"'{patient_name}' 케이스를 삭제하시겠습니까?\n이 작업은 되돌릴 수 없습니다.",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            from desktop.core.database import delete_case
            deleted = delete_case(case_id, self._doctor_id)
            if deleted:
                self.refresh_data()
                self.case_deleted.emit()
            else:
                msgbox.warning(
                    self, "삭제 실패",
                    "본인이 생성한 케이스만 삭제할 수 있습니다.",
                )
        except Exception as exc:
            msgbox.critical(self, "오류", f"삭제 중 오류 발생: {exc}")

    # ── Events ──────────────────────────────────────────────────

    def _on_row_double_clicked(self) -> None:
        """Emit case_selected signal when a row is double-clicked."""
        row = self._table.currentRow()
        if row < 0:
            return
        item = self._table.item(row, 0)
        if item is None:
            return
        case_id = item.data(Qt.ItemDataRole.UserRole)
        if case_id is not None:
            self.case_selected.emit(str(case_id))

    # ── Demo Data ───────────────────────────────────────────────

    @staticmethod
    def _demo_data() -> list[dict]:
        return [
            {
                "id": 1,
                "createdAt": "2026-03-10",
                "patientName": "홍길동",
                "patientBirth": "1965-04-12",
                "patientRegNo": "REG-001",
                "severity": "중등도",
                "finalDecision": "Scarf 절골술",
                "alimtalkSent": True,
                "angleData": json.dumps({
                    "left_surgery": {"severity": "중등도", "final_decision": "Scarf 절골술"},
                    "right_surgery": {"severity": "경증", "final_decision": "Chevron 절골술"},
                }),
            },
            {
                "id": 2,
                "createdAt": "2026-03-09",
                "patientName": "김영희",
                "patientBirth": "1978-11-23",
                "patientRegNo": "REG-002",
                "severity": "중증",
                "finalDecision": "Lapidus 절골술",
                "alimtalkSent": False,
                "angleData": json.dumps({
                    "left_surgery": {"severity": "중증", "final_decision": "Lapidus 절골술"},
                    "right_surgery": {"severity": "중등도", "final_decision": "Scarf 절골술"},
                }),
            },
            {
                "id": 3,
                "createdAt": "2026-03-08",
                "patientName": "이철수",
                "patientBirth": "1990-07-05",
                "patientRegNo": "REG-003",
                "severity": "경증",
                "finalDecision": "Chevron 절골술",
                "alimtalkSent": True,
                "angleData": json.dumps({
                    "left_surgery": {"severity": "경증", "final_decision": "Chevron 절골술"},
                    "right_surgery": {"severity": "경증", "final_decision": "Chevron 절골술"},
                }),
            },
        ]
