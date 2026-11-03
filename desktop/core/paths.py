# -*- coding: utf-8 -*-
"""애플리케이션 기준 경로.

개발 환경에서는 프로젝트 루트를, PyInstaller로 빌드한 경우에는
실행 파일이 있는 폴더를 가리킨다. .env 와 data/ 는 모두
사용자가 직접 열어보거나 런타임에 기록하는 대상이므로
번들 내부(_internal)가 아니라 exe 옆에 두어야 한다.
"""

import os
import sys


def app_root() -> str:
    """.env 와 data/ 가 놓이는 기준 폴더."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def data_dir(*parts: str) -> str:
    """app_root() 아래 data/ 하위 경로. 없으면 만들어 준다."""
    path = os.path.join(app_root(), "data", *parts)
    os.makedirs(path, exist_ok=True)
    return path
