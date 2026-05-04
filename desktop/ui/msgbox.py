"""Styled QMessageBox helpers with visible buttons."""

from PyQt6.QtWidgets import QMessageBox, QWidget

_MSGBOX_STYLE = """
QMessageBox {
    background-color: #ffffff;
}
QMessageBox QLabel {
    color: #2c3e50;
    font-size: 13px;
}
QMessageBox QDialogButtonBox {
    qproperty-centerButtons: true;
}
QMessageBox QPushButton {
    background-color: #3498db;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 8px 20px;
    font-size: 13px;
    font-weight: bold;
    min-width: 80px;
    min-height: 32px;
}
QMessageBox QPushButton:hover {
    background-color: #2980b9;
}
QMessageBox QPushButton:pressed {
    background-color: #2472a4;
}
"""


def _styled(msg: QMessageBox) -> QMessageBox:
    msg.setStyleSheet(_MSGBOX_STYLE)
    return msg


def information(parent: QWidget | None, title: str, text: str) -> QMessageBox.StandardButton:
    msg = QMessageBox(QMessageBox.Icon.Information, title, text, QMessageBox.StandardButton.Ok, parent)
    _styled(msg)
    return msg.exec()


def warning(parent: QWidget | None, title: str, text: str) -> QMessageBox.StandardButton:
    msg = QMessageBox(QMessageBox.Icon.Warning, title, text, QMessageBox.StandardButton.Ok, parent)
    _styled(msg)
    return msg.exec()


def critical(parent: QWidget | None, title: str, text: str) -> QMessageBox.StandardButton:
    msg = QMessageBox(QMessageBox.Icon.Critical, title, text, QMessageBox.StandardButton.Ok, parent)
    _styled(msg)
    return msg.exec()


def question(parent: QWidget | None, title: str, text: str,
             buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
             default: QMessageBox.StandardButton = QMessageBox.StandardButton.No) -> QMessageBox.StandardButton:
    msg = QMessageBox(QMessageBox.Icon.Question, title, text, buttons, parent)
    msg.setDefaultButton(default)
    _styled(msg)
    return msg.exec()
