# -*- mode: python ; coding: utf-8 -*-
"""The PyInstaller recipe for EasyPDF.

Run it from the root of the repository:

    pyinstaller packaging/easypdf.spec --noconfirm

It produces dist/EasyPDF/EasyPDF.exe (a single folder, which starts faster and
draws fewer antivirus false positives than one compressed .exe).
"""

import os
import sys

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))
SRC = os.path.join(ROOT, "src")
ICON = os.path.join(ROOT, "assets", "easypdf.ico")
PNG = os.path.join(ROOT, "assets", "easypdf.png")
VERSION_FILE = os.path.join(SPECPATH, "version_info.txt")

# Qt modules and other dependencies EasyPDF does not use: left out of the package.
EXCLUDES = [
    "tkinter",
    "unittest",
    "pytest",
    "numpy",
    "matplotlib",
    "PIL",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickWidgets",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.Qt3DCore",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtBluetooth",
    "PySide6.QtPositioning",
    "PySide6.QtSerialPort",
]

a = Analysis(
    [os.path.join(SRC, "easypdf", "__main__.py")],
    pathex=[SRC],
    binaries=[],
    datas=[(path, "assets") for path in (ICON, PNG) if os.path.exists(path)],
    hiddenimports=["easypdf", "easypdf.app", "easypdf.ui.main_window"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="EasyPDF",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # a windowed application: no black console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=ICON if os.path.exists(ICON) else None,
    version=VERSION_FILE if (sys.platform == "win32" and os.path.exists(VERSION_FILE)) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="EasyPDF",
)
