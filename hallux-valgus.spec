# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 빌드 설정 — 달려라병원 무지외반증 진료 지원 시스템.

빌드:  venv\Scripts\pyinstaller hallux-valgus.spec --noconfirm
결과:  dist/HalluxValgus/HalluxValgus.exe

.env 와 data/ 는 번들에 넣지 않는다. 실행 파일 옆에 두면
desktop/core/paths.py 의 app_root() 가 찾아간다.
"""

import os

project_root = os.path.abspath(os.getcwd())

a = Analysis(
    ["desktop/main.py"],
    pathex=[project_root],
    binaries=[],
    datas=[("desktop/resources/app.ico", "desktop/resources")],  # 창·작업 표시줄 아이콘
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

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HalluxValgus",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # GUI 앱 — 콘솔 창을 띄우지 않는다
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="desktop/resources/app.ico",  # 병원 로고 (무지외반증 사이트 파비콘과 같음)
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="HalluxValgus",
)
