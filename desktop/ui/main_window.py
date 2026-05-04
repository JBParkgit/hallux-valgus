"""Main application window with navigation and stacked views."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from desktop.ui import msgbox
from desktop.ui.case_workflow_widget import CaseWorkflowWidget
from desktop.ui.dashboard_widget import DashboardWidget


class MainWindow(QMainWindow):
    """Main window with sidebar navigation, dashboard, and case workflow."""

    def __init__(
        self,
        doctor_name: str = "",
        doctor_id: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._doctor_name = doctor_name
        self._doctor_id = doctor_id
        self._init_ui()
        self._refresh_case_list()

    def _init_ui(self) -> None:
        self.setWindowTitle("무지외반증 수술 결정 지원 시스템 - 달려라병원")
        self.setMinimumSize(1200, 800)
        self.showMaximized()

        # Central widget
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── Sidebar ──────────────────────────────────────────────
        sidebar = QWidget()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet("""
            QWidget {
                background-color: #2c3e50;
                color: white;
            }
        """)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # Hospital header
        header = QWidget()
        header.setStyleSheet("background-color: #1a252f; padding: 16px;")
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(16, 20, 16, 20)

        hospital_lbl = QLabel("🏥 달려라병원")
        hospital_lbl.setFont(QFont("맑은 고딕", 14, QFont.Weight.Bold))
        hospital_lbl.setStyleSheet("color: white;")
        header_layout.addWidget(hospital_lbl)

        doctor_lbl = QLabel(f"👨‍⚕️ {self._doctor_name} 선생님")
        doctor_lbl.setStyleSheet("color: #bdc3c7; font-size: 12px; margin-top: 4px;")
        header_layout.addWidget(doctor_lbl)

        sidebar_layout.addWidget(header)

        # Navigation buttons
        self._nav_buttons: list[QPushButton] = []

        nav_items = [
            ("📋  대시보드", 0),
            ("➕  새 케이스", 1),
        ]
        self._nav_new_case_idx = 1

        for label, index in nav_items:
            btn = QPushButton(label)
            btn.setStyleSheet(self._nav_button_style(selected=index == 0))
            btn.setMinimumHeight(48)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, idx=index: self._navigate(idx))
            sidebar_layout.addWidget(btn)
            self._nav_buttons.append(btn)

        # ── Algorithm settings button ─────────────────────────────
        settings_btn = QPushButton("⚙️  알고리즘 설정")
        settings_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #f39c12;
                border: none;
                border-top: 1px solid #34495e;
                text-align: left;
                padding: 10px 20px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #34495e;
            }
        """)
        settings_btn.setMinimumHeight(40)
        settings_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        settings_btn.clicked.connect(self._open_algorithm_settings)
        sidebar_layout.addWidget(settings_btn)

        # ── Case list ─────────────────────────────────────────────
        case_list_lbl = QLabel("  저장된 케이스")
        case_list_lbl.setStyleSheet(
            "color: #95a5a6; font-size: 11px; padding: 8px 12px 2px 12px;"
        )
        sidebar_layout.addWidget(case_list_lbl)

        self._case_list = QListWidget()
        self._case_list.setStyleSheet("""
            QListWidget {
                background-color: #2c3e50;
                border: none;
                color: white;
                font-size: 12px;
            }
            QListWidget::item {
                padding: 8px 16px;
                border-bottom: 1px solid #34495e;
            }
            QListWidget::item:hover {
                background-color: #34495e;
            }
            QListWidget::item:selected {
                background-color: #2980b9;
            }
        """)
        self._case_list.itemClicked.connect(self._on_case_list_clicked)
        self._case_list.setVisible(False)
        sidebar_layout.addWidget(self._case_list, 1)

        # Logout button at bottom
        logout_btn = QPushButton("🚪  로그아웃")
        logout_btn.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                color: #e74c3c;
                border: none;
                border-top: 1px solid #34495e;
                text-align: left;
                padding: 12px 20px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #34495e;
            }
        """)
        logout_btn.setMinimumHeight(48)
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.clicked.connect(self._on_logout)
        sidebar_layout.addWidget(logout_btn)

        main_layout.addWidget(sidebar)

        # ── Content Area (Stacked) ───────────────────────────────
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background-color: #f5f7fa;")

        # Dashboard
        self._dashboard = DashboardWidget(doctor_id=self._doctor_id, parent=self)
        self._dashboard.new_case_requested.connect(lambda: self._navigate(1))
        self._dashboard.case_selected.connect(self._open_case_detail)
        self._dashboard.case_deleted.connect(self._refresh_case_list)
        self._stack.addWidget(self._dashboard)

        # New Case Workflow
        self._case_workflow = CaseWorkflowWidget(
            doctor_name=self._doctor_name,
            parent=self,
        )
        self._case_workflow._doctor_id = self._doctor_id
        self._case_workflow.case_saved.connect(self._on_case_saved)
        self._stack.addWidget(self._case_workflow)

        main_layout.addWidget(self._stack)

        # ── Status Bar ───────────────────────────────────────────
        status_bar = QStatusBar()
        status_bar.setStyleSheet(
            "background-color: #ecf0f1; color: #7f8c8d; padding: 4px 12px;"
        )
        status_bar.showMessage(f"로그인: {self._doctor_name} | 달려라병원 무지외반증 수술 결정 지원 시스템 v1.0")
        self.setStatusBar(status_bar)

    # ── Navigation ──────────────────────────────────────────────

    def _navigate(self, index: int) -> None:
        """Switch stacked widget to the given index and update nav styling."""
        if index == self._nav_new_case_idx:
            if not self._case_workflow.confirm_discard():
                return
            self._case_workflow.reset()
        self._stack.setCurrentIndex(index)
        self._case_list.setVisible(index == self._nav_new_case_idx)
        for i, btn in enumerate(self._nav_buttons):
            btn.setStyleSheet(self._nav_button_style(selected=i == index))

    @staticmethod
    def _nav_button_style(selected: bool) -> str:
        bg = "#3498db" if selected else "transparent"
        hover_bg = "#2980b9" if selected else "#34495e"
        return f"""
            QPushButton {{
                background-color: {bg};
                color: white;
                border: none;
                text-align: left;
                padding: 12px 20px;
                font-size: 13px;
                font-weight: {"bold" if selected else "normal"};
            }}
            QPushButton:hover {{
                background-color: {hover_bg};
            }}
        """

    def _on_logout(self) -> None:
        """Confirm and perform logout."""
        reply = msgbox.question(
            self,
            "로그아웃",
            "정말 로그아웃 하시겠습니까?",
        )
        if reply == QMessageBox.StandardButton.Yes:
            from desktop.ui.login_window import LoginWindow

            self._login = LoginWindow()
            self._login.show()
            self.close()

    def _open_case_detail(self, case_id: str) -> None:
        """Open existing case in the workflow widget for viewing."""
        if not self._case_workflow.confirm_discard():
            return
        self._case_workflow._loading = True
        self._case_workflow._clear_dirty()
        self._navigate(1)
        self._case_workflow._loading = False
        self._case_workflow.load_case(case_id)
        # Highlight in sidebar
        for i in range(self._case_list.count()):
            item = self._case_list.item(i)
            if item and item.data(Qt.ItemDataRole.UserRole) == case_id:
                self._case_list.setCurrentRow(i)
                break

    def _open_algorithm_settings(self) -> None:
        """Open the algorithm settings dialog for this doctor."""
        from desktop.ui.algorithm_settings_dialog import AlgorithmSettingsDialog
        dlg = AlgorithmSettingsDialog(
            doctor_id=self._doctor_id,
            doctor_name=self._doctor_name,
            parent=self,
        )
        if dlg.exec():
            # Config saved; update the workflow widget's config
            self._case_workflow.reload_algorithm_config()

    def _on_case_saved(self) -> None:
        """Handle case saved: refresh lists but stay on current view."""
        self._dashboard.refresh_data()
        self._refresh_case_list()

    def _refresh_case_list(self) -> None:
        """Load saved cases into sidebar list."""
        current_case_id = getattr(self._case_workflow, "_current_case_id", None)
        self._case_list.clear()
        try:
            from desktop.core.database import get_all_cases
            cases = get_all_cases()
            select_row = -1
            for idx, c in enumerate(cases[:50]):
                name = c.get("patientName", "?")
                date = c.get("createdAt")
                date_str = date.strftime("%m/%d %H:%M") if hasattr(date, "strftime") else ""
                text = f"{name}  {date_str}"
                item = QListWidgetItem(text)
                case_id = c.get("id")
                item.setData(Qt.ItemDataRole.UserRole, case_id)
                self._case_list.addItem(item)
                if case_id and case_id == current_case_id:
                    select_row = idx
            if select_row >= 0:
                self._case_list.setCurrentRow(select_row)
        except Exception:
            pass

    def _on_case_list_clicked(self, item: QListWidgetItem) -> None:
        case_id = item.data(Qt.ItemDataRole.UserRole)
        if case_id:
            self._open_case_detail(case_id)
