"""Hallux Valgus Surgery Decision Support System - Desktop Application Entry Point."""

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication

from desktop.ui import theme
from desktop.ui.login_window import LoginWindow


def main() -> None:
    """Launch the desktop application."""
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    theme.apply(app)

    login = LoginWindow()
    login.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
