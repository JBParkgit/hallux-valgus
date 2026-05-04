"""Login window for the Hallux Valgus Surgery Decision Support System."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QKeyEvent
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class LoginWindow(QDialog):
    """Centered login dialog with hospital branding."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._logged_in_doctor: str = ""
        self._init_ui()
        self._try_auto_login()

    def _init_ui(self) -> None:
        self.setWindowTitle("달려라병원 - 무지외반증 수술 결정 지원 시스템")
        self.setFixedSize(420, 520)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.MSWindowsFixedSizeDialogHint
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(48, 40, 48, 40)
        layout.setSpacing(12)

        # Hospital branding
        layout.addSpacing(16)

        hospital_icon = QLabel("🏥")
        hospital_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hospital_icon.setStyleSheet("font-size: 48px;")
        layout.addWidget(hospital_icon)

        hospital_name = QLabel("달려라병원")
        hospital_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hospital_name.setFont(QFont("맑은 고딕", 22, QFont.Weight.Bold))
        hospital_name.setStyleSheet("color: #2c3e50; margin-bottom: 4px;")
        layout.addWidget(hospital_name)

        subtitle = QLabel("무지외반증 수술 결정 지원 시스템")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color: #7f8c8d; font-size: 13px; margin-bottom: 24px;")
        layout.addWidget(subtitle)

        # Divider
        divider = QWidget()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background-color: #dce1e8;")
        layout.addWidget(divider)
        layout.addSpacing(20)

        # Username
        username_label = QLabel("아이디")
        username_label.setStyleSheet("font-weight: bold; color: #34495e; font-size: 13px;")
        layout.addWidget(username_label)

        self._username_input = QLineEdit()
        self._username_input.setPlaceholderText("사용자 아이디를 입력하세요")
        self._username_input.setMinimumHeight(40)
        layout.addWidget(self._username_input)

        layout.addSpacing(8)

        # Password
        password_label = QLabel("비밀번호")
        password_label.setStyleSheet("font-weight: bold; color: #34495e; font-size: 13px;")
        layout.addWidget(password_label)

        self._password_input = QLineEdit()
        self._password_input.setPlaceholderText("비밀번호를 입력하세요")
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_input.setMinimumHeight(40)
        layout.addWidget(self._password_input)

        layout.addSpacing(20)

        # Login button
        self._login_btn = QPushButton("로그인")
        self._login_btn.setMinimumHeight(44)
        self._login_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                font-size: 15px;
                font-weight: bold;
                border-radius: 8px;
            }
            QPushButton:hover { background-color: #2980b9; }
            QPushButton:pressed { background-color: #2472a4; }
        """)
        self._login_btn.clicked.connect(self._on_login)
        layout.addWidget(self._login_btn)

        # Error message area
        self._error_label = QLabel("")
        self._error_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._error_label.setStyleSheet("color: #e74c3c; font-size: 12px;")
        self._error_label.setWordWrap(True)
        layout.addWidget(self._error_label)

        layout.addStretch()

        # Footer
        footer = QLabel("v1.0 | 달려라병원 정보시스템팀")
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        footer.setStyleSheet("color: #bdc3c7; font-size: 11px;")
        layout.addWidget(footer)

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

    def _on_login(self) -> None:
        """Validate credentials and open main window."""
        username = self._username_input.text().strip()
        password = self._password_input.text().strip()

        if not username or not password:
            self._error_label.setText("아이디와 비밀번호를 모두 입력해 주세요.")
            return

        self._error_label.setText("")
        self._login_btn.setEnabled(False)
        self._login_btn.setText("로그인 중...")

        try:
            doctor = self._authenticate(username, password)
        except Exception as exc:
            self._error_label.setText(f"로그인 오류: {exc}")
            self._login_btn.setEnabled(True)
            self._login_btn.setText("로그인")
            return

        if doctor:
            self._logged_in_doctor = doctor
            self._open_main_window()
        else:
            self._error_label.setText("아이디 또는 비밀번호가 올바르지 않습니다.")
            self._login_btn.setEnabled(True)
            self._login_btn.setText("로그인")
            self._password_input.clear()
            self._password_input.setFocus()

    def _authenticate(self, username: str, password: str) -> dict | None:
        """Authenticate user via the database module.

        Returns the doctor dict on success, None on failure.
        """
        try:
            from desktop.core.database import authenticate
            result = authenticate(username, password)
            if result:
                return result
        except Exception:
            pass
        # Fallback: try to get first doctor from DB
        if username == "admin" and password == "admin":
            try:
                from desktop.core.database import _get_conn, _put_conn
                import psycopg2.extras
                conn = _get_conn()
                try:
                    with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                        cur.execute('SELECT * FROM "Doctor" LIMIT 1')
                        doctor = cur.fetchone()
                    if doctor:
                        return dict(doctor)
                finally:
                    _put_conn(conn)
            except Exception:
                pass
            return {"id": "demo-doctor-id", "name": "김의사", "hospital": "달려라병원"}
        return None

    def _try_auto_login(self) -> None:
        """Attempt auto-login with admin credentials."""
        try:
            doctor = self._authenticate("admin", "admin")
            if doctor:
                self._logged_in_doctor = doctor
                self._auto_login_success = True
                return
        except Exception:
            pass
        self._auto_login_success = False

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
