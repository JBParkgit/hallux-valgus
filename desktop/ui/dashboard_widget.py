"""Dashboard widget showing a searchable, sortable list of all cases."""

from __future__ import annotations

import json
from datetime import datetime

from PyQt6.QtCore import QModelIndex, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from desktop.ui import msgbox, theme


class _SeverityDelegate(QStyledItemDelegate):
    """Paints '경증 / 중등도' style text as rounded colour pills."""

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        # Background (hover / selection) from the default style, but no text.
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        style = opt.widget.style() if opt.widget else None
        if style is not None:
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)

        text = index.data(Qt.ItemDataRole.DisplayRole) or ""
        parts = [t.strip() for t in str(text).split("/") if t.strip()]
        if not parts:
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        f = theme.font(9, QFont.Weight.DemiBold)
        painter.setFont(f)
        fm = painter.fontMetrics()
        x = option.rect.x() + 12
        h = 22
        y = option.rect.center().y() - h / 2 + 1
        for part in parts:
            fg, bg = theme.SEVERITY_STYLE.get(part, (theme.MUTED, theme.SURFACE_ALT))
            w = fm.horizontalAdvance(part) + 18
            r = QRectF(x, y, w, h)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(bg))
            painter.drawRoundedRect(r, h / 2, h / 2)
            painter.setPen(QColor(fg))
            painter.drawText(r, Qt.AlignmentFlag.AlignCenter, part)
            x += w + 6
        painter.restore()


class _StatCard(QWidget):
    """Small KPI tile: caption + big number + hint."""

    def __init__(self, caption: str, accent: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        frame = theme.card(self, shadow=False)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(frame)

        ly = QVBoxLayout(frame)
        ly.setContentsMargins(18, 16, 18, 16)
        ly.setSpacing(4)

        top = QHBoxLayout()
        dot = QLabel()
        dot.setFixedSize(8, 8)
        dot.setStyleSheet(f"background-color: {accent}; border-radius: 4px;")
        top.addWidget(dot)
        top.addSpacing(4)
        top.addWidget(theme.label(caption, "overline"))
        top.addStretch()
        ly.addLayout(top)

        self.value = theme.label("0", "value")
        ly.addWidget(self.value)
        self.hint = theme.label("", "caption")
        ly.addWidget(self.hint)


class DashboardWidget(QWidget):
    """Case list table with search, filter, and action buttons."""

    new_case_requested = pyqtSignal()
    case_selected = pyqtSignal(str)  # case_id (CUID string)
    case_deleted = pyqtSignal()  # emitted after successful deletion

    # Column definitions
    _COLUMNS = ["날짜", "환자명", "생년월일", "등록번호", "작성자", "중증도 (좌 / 우)", "수술법", ""]
    _SEVERITY_MAP: dict[str, str] = {
        "mild": "경증", "moderate": "중등도", "severe": "중증",
        "경증": "경증", "중등도": "중등도", "중증": "중증",
    }

    def __init__(self, doctor_id: str = "", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._doctor_id = doctor_id
        self._case_data: list[dict] = []
        self._init_ui()
        self.refresh_data()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 28, 32, 24)
        layout.setSpacing(20)

        # ── Header row ───────────────────────────────────────────
        header_row = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(4)
        titles.addWidget(theme.label("케이스 대시보드", "title"))
        self._subtitle = theme.label("저장된 무지외반증 케이스를 확인하고 관리합니다.", "subtitle")
        titles.addWidget(self._subtitle)
        header_row.addLayout(titles)
        header_row.addStretch()

        refresh_btn = QPushButton("  새로고침")
        theme.set_variant(refresh_btn, "secondary")
        refresh_btn.setIcon(theme.icon("refresh", theme.TEXT_2, 16))
        refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh_btn.clicked.connect(self.refresh_data)
        header_row.addWidget(refresh_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        header_row.addSpacing(8)

        new_case_btn = QPushButton("  새 케이스")
        new_case_btn.setIcon(theme.icon("plus", "#FFFFFF", 16))
        new_case_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        new_case_btn.clicked.connect(self.new_case_requested.emit)
        header_row.addWidget(new_case_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        layout.addLayout(header_row)

        # ── KPI cards ────────────────────────────────────────────
        stats_row = QHBoxLayout()
        stats_row.setSpacing(16)
        self._stat_total = _StatCard("전체 케이스", theme.PRIMARY)
        self._stat_month = _StatCard("이번 달", "#8B7CFF")
        self._stat_sent = _StatCard("알림톡 발송", theme.SUCCESS)
        self._stat_severe = _StatCard("중증 포함", theme.DANGER)
        for c in (self._stat_total, self._stat_month, self._stat_sent, self._stat_severe):
            stats_row.addWidget(c, 1)
        layout.addLayout(stats_row)

        # ── Table card ───────────────────────────────────────────
        table_card = theme.card()
        tc_ly = QVBoxLayout(table_card)
        tc_ly.setContentsMargins(0, 0, 0, 0)
        tc_ly.setSpacing(0)

        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(20, 16, 20, 12)
        toolbar.addWidget(theme.label("케이스 목록", "section"))
        toolbar.addSpacing(8)
        self._count_label = theme.label("0건", "caption")
        toolbar.addWidget(self._count_label)
        toolbar.addStretch()

        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("환자명, 등록번호, 수술법, 작성자 검색")
        self._search_input.addAction(
            theme.icon("search", theme.MUTED, 16), QLineEdit.ActionPosition.LeadingPosition,
        )
        self._search_input.setClearButtonEnabled(True)
        self._search_input.setMinimumHeight(36)
        self._search_input.setFixedWidth(300)
        self._search_input.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self._search_input)
        toolbar.addSpacing(10)
        self._mine_only = QCheckBox("내 케이스만")
        self._mine_only.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mine_only.toggled.connect(lambda _: self._apply_filter(self._search_input.text()))
        toolbar.addWidget(self._mine_only)
        tc_ly.addLayout(toolbar)

        self._table = QTableWidget()
        self._table.setColumnCount(len(self._COLUMNS))
        self._table.setHorizontalHeaderLabels(self._COLUMNS)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setShowGrid(False)
        self._table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._table.setMouseTracking(True)
        self._table.verticalHeader().setVisible(False)
        self._table.verticalHeader().setDefaultSectionSize(48)
        self._table.setSortingEnabled(True)
        self._table.doubleClicked.connect(self._on_row_double_clicked)
        self._table.setItemDelegateForColumn(5, _SeverityDelegate(self._table))
        self._table.setCursor(Qt.CursorShape.PointingHandCursor)
        self._table.setToolTip("더블클릭하여 케이스 열기")

        header = self._table.horizontalHeader()
        header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        header.setHighlightSections(False)
        header.setMinimumSectionSize(80)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(5, 170)
        header.setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(7, QHeaderView.ResizeMode.Fixed)
        header.resizeSection(7, 104)

        tc_ly.addWidget(self._table, 1)

        # Empty state
        self._empty = QWidget()
        em_ly = QVBoxLayout(self._empty)
        em_ly.setContentsMargins(0, 48, 0, 56)
        em_ly.setSpacing(6)
        em_icon = QLabel()
        em_icon.setPixmap(theme.icon("folder", theme.MUTED, 36).pixmap(36, 36))
        em_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        em_ly.addWidget(em_icon)
        self._empty_title = theme.label("아직 저장된 케이스가 없습니다", "section")
        self._empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        em_ly.addWidget(self._empty_title)
        self._empty_hint = theme.label("‘새 케이스’를 눌러 X-ray 측정을 시작하세요.", "caption")
        self._empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        em_ly.addWidget(self._empty_hint)
        self._empty.setVisible(False)
        tc_ly.addWidget(self._empty)

        layout.addWidget(table_card, 1)

    # ── Data ────────────────────────────────────────────────────

    def refresh_data(self) -> None:
        """Reload case list from the server."""
        from desktop.core import api_client
        try:
            self._case_data = api_client.list_cases()
        except api_client.ApiError as exc:
            self._case_data = []
            self._subtitle.setText(f"케이스 목록을 불러오지 못했습니다: {exc.message}")
        else:
            self._subtitle.setText("저장된 무지외반증 케이스를 확인하고 관리합니다. 다른 선생님의 케이스는 읽기 전용입니다.")

        self._update_stats(self._case_data)
        self._apply_filter(self._search_input.text())

    def _update_stats(self, data: list[dict]) -> None:
        now = datetime.now()
        month = 0
        sent = 0
        severe = 0
        for c in data:
            d = c.get("createdAt")
            if hasattr(d, "year") and d.year == now.year and d.month == now.month:
                month += 1
            if c.get("alimtalkSent"):
                sent += 1
            l_sev, r_sev = self._extract_bilateral(c, "severity")
            sevs = {self._SEVERITY_MAP.get(v, v) for v in (l_sev, r_sev, c.get("severity") or "")}
            if "중증" in sevs:
                severe += 1
        total = len(data)
        self._stat_total.value.setText(f"{total:,}")
        self._stat_total.hint.setText("누적 저장 건수")
        self._stat_month.value.setText(f"{month:,}")
        self._stat_month.hint.setText(f"{now.year}년 {now.month}월 신규")
        self._stat_sent.value.setText(f"{sent:,}")
        rate = f"{sent / total * 100:.0f}%" if total else "-"
        self._stat_sent.hint.setText(f"발송률 {rate}")
        self._stat_severe.value.setText(f"{severe:,}")
        self._stat_severe.hint.setText("한쪽 이상 중증 판정")

    def _populate_table(self, data: list[dict]) -> None:
        """Fill the table with given case records."""
        self._table.setSortingEnabled(False)
        self._table.setRowCount(0)
        self._table.setRowCount(len(data))

        bold = theme.font(10, QFont.Weight.DemiBold)
        muted = QColor(theme.TEXT_2)

        for row, case in enumerate(data):
            # 날짜 (DB: createdAt datetime or demo: date string)
            raw_date = case.get("createdAt") or case.get("date", "")
            if hasattr(raw_date, "strftime"):
                date_str = raw_date.strftime("%Y-%m-%d  %H:%M")
            else:
                date_str = str(raw_date) if raw_date else ""
            date_item = QTableWidgetItem(date_str)
            date_item.setData(Qt.ItemDataRole.UserRole, case.get("id", row))
            date_item.setForeground(muted)
            self._table.setItem(row, 0, date_item)

            # 환자명 (DB: patientName)
            name = case.get("patientName") or case.get("patient_name", "")
            name_item = QTableWidgetItem(name)
            name_item.setFont(bold)
            self._table.setItem(row, 1, name_item)

            # 생년월일 (DB: patientBirth)
            birth = case.get("patientBirth") or case.get("birth_date", "")
            birth_item = QTableWidgetItem(str(birth))
            birth_item.setForeground(muted)
            self._table.setItem(row, 2, birth_item)

            # 등록번호 (DB: patientRegNo)
            reg_no = case.get("patientRegNo", "")
            reg_item = QTableWidgetItem(str(reg_no))
            reg_item.setForeground(muted)
            self._table.setItem(row, 3, reg_item)

            # 작성자
            is_mine = case.get("doctorId") == self._doctor_id
            author = case.get("doctorName") or ""
            author_item = QTableWidgetItem(f"{author} (나)" if is_mine else author)
            author_item.setForeground(QColor(theme.PRIMARY) if is_mine else muted)
            self._table.setItem(row, 4, author_item)

            # 중증도 (bilateral: 좌/우) — painted as pills by _SeverityDelegate
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
            self._table.setItem(row, 5, QTableWidgetItem(sev_text))

            # 수술법 (bilateral: 좌/우)
            left_surg, right_surg = self._extract_bilateral(case, "surgery")
            if left_surg and right_surg:
                surgery_text = f"{left_surg}  /  {right_surg}"
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
            self._table.setItem(row, 6, QTableWidgetItem(surgery_text))

            # 삭제 버튼 (본인 케이스만)
            case_id = case.get("id", "")
            if not is_mine:
                lock = QLabel("읽기 전용")
                lock.setStyleSheet(f"color: {theme.MUTED}; font-size: 11px; padding-right: 16px;")
                lock.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self._table.setCellWidget(row, 7, lock)
                continue
            holder = QWidget()
            h_ly = QHBoxLayout(holder)
            h_ly.setContentsMargins(0, 0, 12, 0)
            h_ly.addStretch()
            del_btn = QPushButton("삭제")
            theme.set_variant(del_btn, "danger-ghost")
            del_btn.setIcon(theme.icon("trash", theme.MUTED, 14))
            del_btn.setMinimumWidth(72)
            del_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            del_btn.clicked.connect(
                lambda checked, cid=str(case_id), nm=name: self._on_delete_clicked(cid, nm)
            )
            h_ly.addWidget(del_btn)
            self._table.setCellWidget(row, 7, holder)

        self._table.setSortingEnabled(True)
        self._count_label.setText(f"{len(data)}건")

        has_rows = bool(data)
        self._table.setVisible(has_rows)
        self._empty.setVisible(not has_rows)
        if not has_rows and self._case_data:
            self._empty_title.setText("검색 결과가 없습니다")
            self._empty_hint.setText("다른 검색어로 다시 시도해 보세요.")
        elif not has_rows:
            self._empty_title.setText("아직 저장된 케이스가 없습니다")
            self._empty_hint.setText("‘새 케이스’를 눌러 X-ray 측정을 시작하세요.")

    # ── Filter ──────────────────────────────────────────────────

    def _apply_filter(self, text: str) -> None:
        """Filter table rows by search text."""
        query = text.strip().lower()
        base = self._case_data
        if self._mine_only.isChecked():
            base = [c for c in base if c.get("doctorId") == self._doctor_id]
        if not query:
            self._populate_table(base)
            return

        filtered = [
            c
            for c in base
            if query in (c.get("doctorName") or "").lower()
            or query in (c.get("patientName") or c.get("patient_name", "")).lower()
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

        from desktop.core import api_client
        try:
            api_client.delete_case(case_id)
        except api_client.ApiError as exc:
            msgbox.warning(self, "삭제 실패", exc.message)
            return
        self.refresh_data()
        self.case_deleted.emit()

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
