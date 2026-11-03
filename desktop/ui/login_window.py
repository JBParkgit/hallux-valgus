"""Login window for the Hallux Valgus Surgery Decision Support System."""

from __future__ import annotations

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QKeyEvent
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from desktop.ui import theme


class LoginWindow(QDialog):
    """Centered login dialog with hospital branding."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._logged_in_doctor: dict = {}
        self._settings = QSettings("달려라병원", "HalluxValgus")
        self._init_ui()
        self._restore_username()

    def _init_ui(self) -> None:
        self.setWindowTitle("달려라병원 - 무지외반증 수술 결정 지원 시스템")
        self.setFixedSize(460, 600)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.MSWindowsFixedSizeDialogHint
        )

        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 28, 28, 20)
        outer.setSpacing(0)

        panel = theme.card(shadow=True)
        outer.addWidget(panel, 1)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(36, 36, 36, 32)
        layout.setSpacing(0)

        # ── Brand ────────────────────────────────────────────────
        logo = QLabel()
        logo.setPixmap(theme.logo_pixmap(52))
        logo.setFixedSize(52, 52)
        layout.addWidget(logo, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addSpacing(20)

        hospital_name = theme.label("달려라병원", "title")
        layout.addWidget(hospital_name)
        layout.addSpacing(4)

        subtitle = theme.label("무지외반증 수술 결정 지원 시스템", "subtitle")
        layout.addWidget(subtitle)
        layout.addSpacing(28)

        # ── Username ─────────────────────────────────────────────
        layout.addWidget(theme.label("아이디", "field"))
        layout.addSpacing(6)
        self._username_input = QLineEdit()
        self._username_input.setPlaceholderText("사용자 아이디")
        self._username_input.setMinimumHeight(42)
        self._username_input.addAction(
            theme.icon("user", theme.MUTED), QLineEdit.ActionPosition.LeadingPosition,
        )
        layout.addWidget(self._username_input)
        layout.addSpacing(14)

        # ── Password ─────────────────────────────────────────────
        layout.addWidget(theme.label("비밀번호", "field"))
        layout.addSpacing(6)
        self._password_input = QLineEdit()
        self._password_input.setPlaceholderText("비밀번호")
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_input.setMinimumHeight(42)
        layout.addWidget(self._password_input)
        layout.addSpacing(22)

        # ── Login button ─────────────────────────────────────────
        self._login_btn = QPushButton("로그인")
        self._login_btn.setProperty("size", "lg")
        self._login_btn.setMinimumHeight(46)
        self._login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._login_btn.clicked.connect(self._on_login)
        layout.addWidget(self._login_btn)
        layout.addSpacing(10)

        self._error_label = theme.label("", "error")
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.setWordWrap(True)
        layout.addWidget(self._error_label)

        layout.addStretch()

        # Footer
        footer = theme.label("v1.0  ·  달려라병원 정보시스템팀", "caption")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addSpacing(14)
        outer.addWidget(footer)

        # Focus username on open
        self._username_input.setFocus()

    def keyPressEvent(self, event: QKeyEvent | None) -> None:  # type: ignore[override]
        """Handle Enter key to trigger login."""
        if event and event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        ):
            self._on_login()
        else:
            super().keyPressEvent(event)

    def _restore_username(self) -> None:
        """Pre-fill the last used username (never the password)."""
        last = str(self._settings.value("last_username", "") or "")
        if last:
            self._username_input.setText(last)
            self._password_input.setFocus()

    def _on_login(self) -> None:
        """Log in through the server and open the main window."""
        from desktop.core import api_client

        username = self._username_input.text().strip()
        password = self._password_input.text()

        if not username or not password:
            self._error_label.setText("아이디와 비밀번호를 모두 입력해 주세요.")
            return

        self._error_label.setText("")
        self._login_btn.setEnabled(False)
        self._login_btn.setText("로그인 중...")
        QApplication.processEvents()

        try:
            doctor = api_client.login(username, password)
        except api_client.ApiError as exc:
            self._error_label.setText(exc.message)
            self._login_btn.setEnabled(True)
            self._login_btn.setText("로그인")
            if exc.status == 401:
                self._password_input.clear()
                self._password_input.setFocus()
            return

        self._settings.setValue("last_username", username)
        self._logged_in_doctor = doctor
        self._open_main_window()

    def _open_main_window(self) -> None:
        """Open the main application window and close login."""
        from desktop.ui.main_window import MainWindow

        doctor = self._logged_in_doctor
        self._main_window = MainWindow(
            doctor_name=doctor.get("name", ""),
            doctor_id=doctor.get("id", ""),
        )
        self._main_window.show()
        self.close()
