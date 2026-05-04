"""Hallux Valgus Surgery Decision Support System - Desktop Application Entry Point."""

import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from desktop.ui.login_window import LoginWindow


def main() -> None:
    """Launch the desktop application."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Set Korean-friendly font
    font = QFont("맑은 고딕", 10)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)

    # Global stylesheet - modern, clean look
    app.setStyleSheet("""
        QMainWindow, QDialog, QWidget {
            background-color: #f5f7fa;
            color: #2c3e50;
        }
        QPushButton {
            background-color: #3498db;
            color: white;
            border: none;
            border-radius: 6px;
            padding: 8px 20px;
            font-size: 13px;
            font-weight: bold;
            min-height: 32px;
        }
        QPushButton:hover {
            background-color: #2980b9;
        }
        QPushButton:pressed {
            background-color: #2472a4;
        }
        QPushButton:disabled {
            background-color: #bdc3c7;
            color: #95a5a6;
        }
        QPushButton[class="danger"] {
            background-color: #e74c3c;
        }
        QPushButton[class="danger"]:hover {
            background-color: #c0392b;
        }
        QPushButton[class="success"] {
            background-color: #27ae60;
        }
        QPushButton[class="success"]:hover {
            background-color: #219a52;
        }
        QPushButton[class="secondary"] {
            background-color: #95a5a6;
        }
        QPushButton[class="secondary"]:hover {
            background-color: #7f8c8d;
        }
        QLineEdit, QTextEdit, QComboBox, QSpinBox {
            border: 2px solid #dce1e8;
            border-radius: 6px;
            padding: 8px 12px;
            background-color: white;
            font-size: 13px;
            min-height: 20px;
        }
        QLineEdit:focus, QTextEdit:focus, QComboBox:focus {
            border-color: #3498db;
        }
        QTableWidget {
            border: 1px solid #dce1e8;
            border-radius: 6px;
            background-color: white;
            gridline-color: #ecf0f1;
            selection-background-color: #3498db;
            selection-color: white;
        }
        QTableWidget::item {
            padding: 6px;
        }
        QHeaderView::section {
            background-color: #ecf0f1;
            color: #2c3e50;
            padding: 8px;
            border: none;
            border-bottom: 2px solid #bdc3c7;
            font-weight: bold;
        }
        QGroupBox {
            font-weight: bold;
            border: 2px solid #dce1e8;
            border-radius: 8px;
            margin-top: 12px;
            padding-top: 16px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 16px;
            padding: 0 8px;
        }
        QLabel[class="heading"] {
            font-size: 18px;
            font-weight: bold;
            color: #2c3e50;
        }
        QLabel[class="subheading"] {
            font-size: 14px;
            color: #7f8c8d;
        }
        QCheckBox, QRadioButton {
            spacing: 8px;
            font-size: 13px;
        }
        QCheckBox::indicator, QRadioButton::indicator {
            width: 18px;
            height: 18px;
            border: 2px solid #999;
            border-radius: 3px;
            background-color: #fff;
        }
        QCheckBox::indicator:checked, QRadioButton::indicator:checked {
            background-color: #333;
            border-color: #333;
        }
        QRadioButton::indicator {
            border-radius: 9px;
        }
        QRadioButton::indicator:checked {
            background-color: #333;
            border-color: #333;
        }
        QScrollBar:vertical {
            border: none;
            background: #f5f7fa;
            width: 10px;
            border-radius: 5px;
        }
        QScrollBar::handle:vertical {
            background: #bdc3c7;
            border-radius: 5px;
            min-height: 30px;
        }
        QScrollBar::handle:vertical:hover {
            background: #95a5a6;
        }
    """)

    login = LoginWindow()
    if getattr(login, "_auto_login_success", False):
        # Auto-login succeeded — go straight to main window
        login._open_main_window()
    else:
        login.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
