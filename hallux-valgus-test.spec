# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 빌드 설정 — 의료진 검토용 테스트 버전 (서버 미연결, 파일 하나).

빌드:  venv\Scripts\pyinstaller hallux-valgus-test.spec --noconfirm --distpath dist-desktop --workpath build-desktop
결과:  dist-desktop/무지외반증_테스트버전.exe

화면은 실제 프로그램과 같고, 서버 대신 %LOCALAPPDATA%\HalluxValgusTest 에 저장한다.
(desktop/main_test.py, desktop/core/offline_backend.py 참고)
"""

import os

project_root = os.path.abspath(os.getcwd())

a = Analysis(
    ["desktop/main_test.py"],
    pathex=[project_root],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    runtime_hooks=[],
    # 앱이 쓰지 않는 Qt 모듈·툴킷을 빼서 배포 용량을 줄인다.
    excludes=[
        "PyQt6.QtWebEngineCore",
        "PyQt6.QtWebEngineWidgets",
        "PyQt6.QtQml",
        "PyQt6.QtQuick",
        "PyQt6.QtQuick3D",
        "PyQt6.QtMultimedia",
        "PyQt6.QtBluetooth",
        "PyQt6.QtNetworkAuth",
        "PyQt6.QtPositioning",
        "PyQt6.QtSensors",
        "PyQt6.QtSerialPort",
        "PyQt6.QtTest",
        "PyQt6.QtDesigner",
        "PyQt6.Qt3DCore",
        "PyQt6.Qt3DRender",
        "PyQt6.QtCharts",
        "PyQt6.QtDataVisualization",
        "tkinter",
        "matplotlib",
        "numpy",
        "pytest",
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

# 파일 하나(onefile)로 만든다 — 의료진에게 exe 하나만 보내면 되도록
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="무지외반증_테스트버전",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
