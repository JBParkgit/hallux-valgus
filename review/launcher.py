# -*- coding: utf-8 -*-
"""의료진 검토 도구 실행기.

번들된 clinical-review.html 을 이 PC의 고정 위치
(%LOCALAPPDATA%\\HalluxValgusReview\\) 에 풀어 기본 브라우저로 엽니다.
위치가 매번 같아야 브라우저에 자동 저장된 검토 내용이 다음 실행 때도 이어집니다.

빌드:
  venv\\Scripts\\pyinstaller --onefile --windowed --name 무지외반증_판정검토 ^
      --add-data "review/clinical-review.html;." ^
      --distpath dist-desktop/review --workpath build-desktop/review ^
      --specpath build-desktop/review review/launcher.py
"""

import os
import shutil
import sys
import webbrowser
from pathlib import Path

HTML_NAME = "clinical-review.html"


def _bundled_html() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / HTML_NAME


def _install_dir() -> Path:
    root = os.environ.get("LOCALAPPDATA") or str(Path.home())
    d = Path(root) / "HalluxValgusReview"
    d.mkdir(parents=True, exist_ok=True)
    return d


def main() -> None:
    src = _bundled_html()
    dest = _install_dir() / HTML_NAME
    # 새 버전이면 덮어쓴다 (검토 내용은 브라우저 저장소에 있으므로 유지됨)
    if not dest.exists() or dest.read_bytes() != src.read_bytes():
        shutil.copyfile(src, dest)
    webbrowser.open(dest.as_uri())


if __name__ == "__main__":
    main()
