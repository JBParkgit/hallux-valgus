"""Main application window with navigation and stacked views."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from desktop.ui import msgbox, theme


def api_client_is_admin() -> bool:
    from desktop.core import api_client
    return api_client.is_admin()
from desktop.ui.case_workflow_widget import CaseWorkflowWidget
from desktop.ui.dashboard_widget import DashboardWidget


_SIDEBAR_QSS = f"""
    QWidget#sidebar {{
        background-color: {theme.SIDEBAR};
    }}
    QWidget#sidebar QLabel {{ color: {theme.SIDEBAR_TEXT}; background: transparent; }}
    QLabel#brandName {{ color: white; font-size: 15px; font-weight: 700; }}
    QLabel#brandSub {{ color: {theme.SIDEBAR_MUTED}; font-size: 11px; }}
    QLabel#sideSection {{
        color: {theme.SIDEBAR_MUTED}; font-size: 11px; font-weight: 600;
        padding: 0 8px;
    }}
    QPushButton[nav="true"] {{
        background-color: transparent;
        color: {theme.SIDEBAR_TEXT};
        border: none;
        border-radius: 8px;
        text-align: left;
        padding: 9px 12px;
        font-size: 13px;
        font-weight: 500;
    }}
    QPushButton[nav="true"]:hover {{
        background-color: {theme.SIDEBAR_HOVER};
        color: white;
    }}
    QPushButton[nav="true"]:checked {{
        background-color: {theme.PRIMARY};
        color: white;
        font-weight: 600;
    }}
    QListWidget#caseList {{
        background-color: transparent;
        border: none;
        color: {theme.SIDEBAR_TEXT};
        font-size: 12px;
        outline: none;
    }}
    QListWidget#caseList::item {{
        padding: 7px 10px;
        border-radius: 7px;
        margin: 1px 0;
    }}
    QListWidget#caseList::item:hover {{
        background-color: {theme.SIDEBAR_HOVER};
        color: white;
    }}
    QListWidget#caseList::item:selected {{
        background-color: #1F2C4A;
        color: white;
    }}
    QWidget#profile {{
        background-color: {theme.SIDEBAR_HOVER};
        border-radius: 10px;
    }}
    QWidget#sidebar QLabel#avatar {{
        background-color: {theme.PRIMARY};
        color: white;
        border-radius: 16px;
        font-weight: 700;
        font-size: 13px;
    }}
    QLabel#profileName {{ color: white; font-size: 13px; font-weight: 600; }}
    QLabel#profileRole {{ color: {theme.SIDEBAR_MUTED}; font-size: 11px; }}
    QPushButton#logoutBtn {{
        background: transparent; border: none; border-radius: 6px;
        padding: 6px; min-height: 0;
    }}
    QPushButton#logoutBtn:hover {{ background-color: #26324F; }}
    QScrollBar:vertical {{ width: 6px; }}
    QScrollBar::handle:vertical {{ background: #2A3654; }}
"""


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
        sidebar.setObjectName("sidebar")
        sidebar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        sidebar.setFixedWidth(232)
        sidebar.setStyleSheet(_SIDEBAR_QSS)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(14, 20, 14, 14)
        sidebar_layout.setSpacing(4)

        # Brand header
        brand = QHBoxLayout()
        brand.setSpacing(10)
        logo = QLabel()
        logo.setPixmap(theme.logo_pixmap(34))
        logo.setFixedSize(34, 34)
        brand.addWidget(logo)
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        name_lbl = QLabel("달려라병원")
        name_lbl.setObjectName("brandName")
        sub_lbl = QLabel("Hallux Valgus CDS")
        sub_lbl.setObjectName("brandSub")
        brand_text.addWidget(name_lbl)
        brand_text.addWidget(sub_lbl)
        brand.addLayout(brand_text)
        brand.addStretch()
        sidebar_layout.addLayout(brand)
        sidebar_layout.addSpacing(24)

        menu_lbl = QLabel("메뉴")
        menu_lbl.setObjectName("sideSection")
        sidebar_layout.addWidget(menu_lbl)
        sidebar_layout.addSpacing(4)

        # Navigation buttons
        self._nav_buttons: list[QPushButton] = []

        nav_items = [
            ("대시보드", "dashboard", 0),
            ("새 케이스", "plus", 1),
        ]
        self._nav_new_case_idx = 1

        for label, icon_name, index in nav_items:
            btn = self._make_nav_button(label, icon_name)
            btn.setCheckable(True)
            btn.setChecked(index == 0)
            btn.clicked.connect(lambda checked, idx=index: self._navigate(idx))
            sidebar_layout.addWidget(btn)
            self._nav_buttons.append(btn)

        # ── Admin (관리자만) ───────────────────────────────────────
        from desktop.core import api_client
        self._is_admin = api_client.is_admin()
        self._admin_idx = 2
        if self._is_admin:
            admin_btn = self._make_nav_button("관리자", "shield")
            admin_btn.setCheckable(True)
            admin_btn.clicked.connect(lambda checked: self._navigate(self._admin_idx))
            sidebar_layout.addWidget(admin_btn)
            self._nav_buttons.append(admin_btn)

        # ── Algorithm settings button ─────────────────────────────
        settings_btn = self._make_nav_button("알고리즘 설정", "settings")
        settings_btn.clicked.connect(self._open_algorithm_settings)
        sidebar_layout.addWidget(settings_btn)

        # ── Case list ─────────────────────────────────────────────
        sidebar_layout.addSpacing(18)
        self._case_list_lbl = QLabel("저장된 케이스")
        self._case_list_lbl.setObjectName("sideSection")
        self._case_list_lbl.setVisible(False)
        sidebar_layout.addWidget(self._case_list_lbl)

        self._case_list = QListWidget()
        self._case_list.setObjectName("caseList")
        self._case_list.itemClicked.connect(self._on_case_list_clicked)
        self._case_list.setVisible(False)
        sidebar_layout.addWidget(self._case_list, 1)

        self._sidebar_spacer = QWidget()
        sidebar_layout.addWidget(self._sidebar_spacer, 1)

        # ── Profile + logout ───────────────────────────────────────
        profile = QWidget()
        profile.setObjectName("profile")
        profile.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        prof_ly = QHBoxLayout(profile)
        prof_ly.setContentsMargins(10, 10, 6, 10)
        prof_ly.setSpacing(6)

        avatar = QLabel((self._doctor_name or "?")[:1])
        avatar.setObjectName("avatar")
        avatar.setFixedSize(32, 32)
        avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        prof_ly.addWidget(avatar)

        prof_text = QVBoxLayout()
        prof_text.setSpacing(0)
        pn = QLabel(f"{self._doctor_name} 선생님")
        pn.setObjectName("profileName")
        pr = QLabel("관리자" if api_client_is_admin() else "달려라병원")
        pr.setObjectName("profileRole")
        prof_text.addWidget(pn)
        prof_text.addWidget(pr)
        prof_ly.addLayout(prof_text, 1)

        pw_btn = QPushButton()
        pw_btn.setObjectName("logoutBtn")
        pw_btn.setIcon(theme.icon("key", theme.SIDEBAR_TEXT))
        pw_btn.setIconSize(theme.ICON_SIZE)
        pw_btn.setToolTip("비밀번호 변경")
        pw_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        pw_btn.clicked.connect(self._change_password)
        prof_ly.addWidget(pw_btn)

        logout_btn = QPushButton()
        logout_btn.setObjectName("logoutBtn")
        logout_btn.setIcon(theme.icon("logout", theme.SIDEBAR_TEXT))
        logout_btn.setIconSize(theme.ICON_SIZE)
        logout_btn.setToolTip("로그아웃")
        logout_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        logout_btn.clicked.connect(self._on_logout)
        prof_ly.addWidget(logout_btn)

        sidebar_layout.addSpacing(8)
        sidebar_layout.addWidget(profile)

        main_layout.addWidget(sidebar)

        # ── Content Area (Stacked) ───────────────────────────────
        self._stack = QStackedWidget()

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
        self._case_workflow.reload_algorithm_config()  # this doctor's settings
        self._case_workflow.case_saved.connect(self._on_case_saved)
        self._stack.addWidget(self._case_workflow)

        # Admin
        if self._is_admin:
            from desktop.ui.admin_widget import AdminWidget
            self._admin = AdminWidget(self)
            self._admin.data_changed.connect(self._on_admin_changed)
            self._stack.addWidget(self._admin)

        main_layout.addWidget(self._stack)

        # ── Status Bar ───────────────────────────────────────────
        status_bar = QStatusBar()
        status_bar.showMessage(
            f"  로그인: {self._doctor_name}  ·  달려라병원 무지외반증 수술 결정 지원 시스템 v1.0"
        )
        self.setStatusBar(status_bar)

    @staticmethod
    def _make_nav_button(label: str, icon_name: str) -> QPushButton:
        btn = QPushButton(f"  {label}")
        btn.setProperty("nav", True)
        btn.setIcon(theme.icon(icon_name, theme.SIDEBAR_TEXT))
        btn.setIconSize(theme.ICON_SIZE)
        btn.setMinimumHeight(40)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        return btn

    # ── Navigation ──────────────────────────────────────────────

    def _navigate(self, index: int) -> None:
        """Switch stacked widget to the given index and update nav styling."""
        if index == self._nav_new_case_idx:
            if not self._case_workflow.confirm_discard():
                self._sync_nav_checked(self._stack.currentIndex())
                return
            self._case_workflow.reset()
        self._stack.setCurrentIndex(index)
        if self._is_admin and index == self._admin_idx:
            self._admin.refresh()
        elif index == 0:
            self._dashboard.refresh_data()
        show_list = index == self._nav_new_case_idx
        self._case_list.setVisible(show_list)
        self._case_list_lbl.setVisible(show_list)
        self._sidebar_spacer.setVisible(not show_list)
        self._sync_nav_checked(index)

    def _sync_nav_checked(self, index: int) -> None:
        for i, btn in enumerate(self._nav_buttons):
            btn.setChecked(i == index)

    def _on_admin_changed(self) -> None:
        """Users or cases changed in the admin screen → refresh other views."""
        self._dashboard.refresh_data()
        self._refresh_case_list()

    def _change_password(self) -> None:
        from desktop.ui.password_dialog import PasswordDialog
        PasswordDialog(self).exec()

    def _on_logout(self) -> None:
        """Confirm and perform logout."""
        reply = msgbox.question(
            self,
            "로그아웃",
            "정말 로그아웃 하시겠습니까?",
        )
        if reply == QMessageBox.StandardButton.Yes:
            if not self._case_workflow.confirm_discard():
                return
            from desktop.core import api_client
            from desktop.ui.login_window import LoginWindow

            api_client.logout()

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
            from desktop.core import api_client
            cases = api_client.list_cases()
            select_row = -1
            for idx, c in enumerate(cases[:50]):
                name = c.get("patientName", "?")
                date = c.get("createdAt")
                date_str = date.strftime("%m/%d %H:%M") if hasattr(date, "strftime") else ""
                text = f"{name}   ·   {date_str}" if date_str else name
                if c.get("doctorId") != self._doctor_id:
                    text += f"   ({c.get('doctorName', '')})"
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
