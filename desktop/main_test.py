# -*- coding: utf-8 -*-
"""테스트 버전 실행 시작점 — 실제 프로그램과 같은 화면, 서버 연결 없음.

의료진이 측정·수술 추천 화면을 직접 써 보며 검토할 수 있도록 만든 버전입니다.
- 서버 대신 이 PC(%LOCALAPPDATA%\\HalluxValgusTest)에만 저장합니다.
- 로그인 없이 바로 시작하고, 알림톡·환자 리포트는 만들어지지 않습니다.
- 환자 정보는 EMR 파일 대신 가상의 '테스트환자'로 채워집니다 (화면에서 수정 가능).

실행:  venv\\Scripts\\python -m desktop.main_test
빌드:  venv\\Scripts\\pyinstaller hallux-valgus-test.spec --noconfirm
"""

import os
import sys

from desktop.core import paths

# 1) 저장 위치를 실제 프로그램과 분리한다 (다른 모듈이 import 시점에 data_dir 을 쓰므로 가장 먼저)
_TEST_ROOT = os.path.join(os.environ.get("LOCALAPPDATA") or os.path.expanduser("~"), "HalluxValgusTest")
os.makedirs(_TEST_ROOT, exist_ok=True)
paths.app_root = lambda: _TEST_ROOT  # type: ignore[assignment]

# 2) 서버 통신을 PC 내부 저장으로 교체
from desktop.core import offline_backend  # noqa: E402

offline_backend.install()

# 3) EMR 환자 파일 대신 가상의 테스트 환자
from desktop.core import patient_parser  # noqa: E402

_TEST_PATIENT = {
    "birth": "650315", "birth_date": "650315", "phone": "010-0000-0000",
    "name": "테스트환자", "reg_no": "T0001", "disease_code": "",
}


def _test_patients(filepath: str = "") -> list[dict]:
    p = dict(_TEST_PATIENT)
    p["age"] = patient_parser.calculate_age(p["birth"])
    return [p]


patient_parser.load_patients = _test_patients  # type: ignore[assignment]

from PyQt6.QtCore import Qt  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402

from desktop.ui import msgbox, theme  # noqa: E402
from desktop.ui.main_window import MainWindow  # noqa: E402

TEST_TAG = "  [테스트 버전 · 서버 미연결]"

# 창 제목에 테스트 버전임을 항상 표시 (로그아웃 후 다시 열린 창 포함)
_orig_set_title = MainWindow.setWindowTitle
MainWindow.setWindowTitle = lambda self, t: _orig_set_title(self, t if TEST_TAG in t else t + TEST_TAG)  # type: ignore[method-assign]

WELCOME = (
    "무지외반증 수술 결정 지원 시스템의 테스트 버전입니다.\n\n"
    "• 화면과 측정·수술 추천 동작은 실제 프로그램과 같습니다.\n"
    "• 저장한 케이스는 이 PC에만 저장되며 병원 서버로 가지 않습니다.\n"
    "• 알림톡은 실제로 발송되지 않고, 환자 리포트도 만들어지지 않습니다.\n"
    "• 환자 정보는 가상의 '테스트환자'입니다. 화면에서 직접 바꿀 수 있습니다.\n\n"
    "X-ray는 PACS 등에서 복사한 뒤 측정 화면에서 Ctrl+V로 붙여넣으세요."
)


def main() -> None:
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    theme.apply(app)

    doctor = offline_backend.login(os.environ.get("HV_TEST_DOCTOR", "테스트 원장"))
    window = MainWindow(doctor_name=doctor["name"], doctor_id=doctor["id"])
    window.showMaximized()
    msgbox.information(window, "테스트 버전", WELCOME)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
