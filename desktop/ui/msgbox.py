"""Styled QMessageBox helpers with visible buttons."""

from PyQt6.QtWidgets import QMessageBox, QWidget

def _styled(msg: QMessageBox) -> QMessageBox:
    """Apply theme tweaks: non-default buttons render as secondary."""
    from desktop.ui import theme

    # Only the text label gets a min width (not the icon label)
    msg.setStyleSheet(
        "QMessageBox { background-color: %s; } QLabel#qt_msgbox_label { min-width: 260px; }" % theme.SURFACE
    )
    secondary_roles = {
        QMessageBox.ButtonRole.RejectRole,
        QMessageBox.ButtonRole.NoRole,
    }
    for btn in msg.buttons():
        if msg.buttonRole(btn) in secondary_roles:
            theme.set_variant(btn, "secondary")
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
