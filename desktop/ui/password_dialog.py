"""Change-password dialog (server account)."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLineEdit, QPushButton, QVBoxLayout, QWidget

from desktop.ui import msgbox, theme


class PasswordDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("비밀번호 변경")
        self.setFixedWidth(400)

        ly = QVBoxLayout(self)
        ly.setContentsMargins(28, 24, 28, 22)
        ly.setSpacing(6)

        ly.addWidget(theme.label("비밀번호 변경", "title"))
        hint = theme.label("변경하면 다른 PC에 로그인된 상태는 모두 로그아웃됩니다.", "subtitle")
        hint.setWordWrap(True)
        ly.addWidget(hint)
        ly.addSpacing(14)

        self._current = self._field(ly, "현재 비밀번호")
        self._new = self._field(ly, "새 비밀번호")
        self._confirm = self._field(ly, "새 비밀번호 확인")

        self._error = theme.label("", "error")
        self._error.setWordWrap(True)
        ly.addSpacing(4)
        ly.addWidget(self._error)
        ly.addSpacing(10)

        row = QHBoxLayout()
        row.addStretch()
        cancel = QPushButton("취소")
        theme.set_variant(cancel, "secondary")
        cancel.setMinimumWidth(90)
        cancel.clicked.connect(self.reject)
        row.addWidget(cancel)
        self._ok = QPushButton("변경")
        self._ok.setMinimumWidth(100)
        self._ok.setDefault(True)
        self._ok.clicked.connect(self._submit)
        row.addWidget(self._ok)
        ly.addLayout(row)

        self._current.setFocus()

    @staticmethod
    def _field(ly: QVBoxLayout, label: str) -> QLineEdit:
        ly.addWidget(theme.label(label, "field"))
        edit = QLineEdit()
        edit.setEchoMode(QLineEdit.EchoMode.Password)
        edit.setMinimumHeight(38)
        ly.addWidget(edit)
        ly.addSpacing(6)
        return edit

    def _submit(self) -> None:
        current = self._current.text()
        new = self._new.text()
        if not current or not new:
            self._error.setText("모든 칸을 입력해 주세요.")
            return
        if new != self._confirm.text():
            self._error.setText("새 비밀번호가 서로 일치하지 않습니다.")
            self._confirm.clear()
            self._confirm.setFocus()
            return

        from desktop.core import api_client
        self._ok.setEnabled(False)
        self._error.setText("")
        try:
            api_client.change_password(current, new)
        except api_client.ApiError as e:
            self._error.setText(e.message)
            self._ok.setEnabled(True)
            if "현재 비밀번호" in e.message:
                self._current.clear()
                self._current.setFocus()
            return
        msgbox.information(self, "비밀번호 변경", "비밀번호가 변경되었습니다.")
        self.accept()

    def keyPressEvent(self, event) -> None:  # type: ignore[override]
        if event and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._submit()
        else:
            super().keyPressEvent(event)
