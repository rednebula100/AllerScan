# -*- mode: python ; coding: utf-8 -*-
"""AllerScan PyInstaller 스펙: 단일 exe(onefile) + 콘솔 없음(windowed).

빌드 전에 assets/icon.ico가 있어야 한다 (tools/generate_icon.py 또는 build.bat이 생성).
    pyinstaller AllerScan.spec
"""

# customtkinter는 테마 JSON 등 자체 데이터 파일을 갖고 있는데, 이는 실행에 필수적이라
# 명시적으로 datas에 포함해야 한다 (pyinstaller-hooks-contrib의 hook-customtkinter.py가
# collect_data_files로 자동 수집해주지만, 여기서도 안전하게 한 번 더 명시한다).
from PyInstaller.utils.hooks import collect_data_files

datas = collect_data_files("customtkinter")

# plyer는 sys.platform에 따라 알림 백엔드를 런타임에 동적 import하므로
# PyInstaller의 정적 분석이 놓친다. Windows 알림 모듈을 명시적으로 포함한다.
hiddenimports = [
    "plyer.platforms.win.notification",
]

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="AllerScan",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # windowed 모드: 콘솔 창 없음
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="assets/icon.ico",
)
