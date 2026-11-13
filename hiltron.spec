# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

import skyfield

skyfield_data_dir = str(Path(skyfield.__file__).parent / "data")

datas = [
    ("frontend", "frontend"),
    ("backend/de421.bsp", "backend"),
    ("backend/data", "backend/data"),
    ("assets", "assets"),
    (skyfield_data_dir, "skyfield/data"),
]
datas += collect_data_files("webview")
datas += collect_data_files("pythonnet")
datas += collect_data_files("certifi")

hiddenimports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "uvicorn.lifespan.off",
    "websockets",
    "websockets.legacy",
    "websockets.legacy.server",
    "backend",
    "backend.main",
    "backend.paths",
    "backend.astronomy",
    "backend.astronomy.engine",
    "backend.ai",
    "backend.ai.predictive_cache",
    "skyfield",
    "jplephem",
    "sgp4",
    "hijridate",
    "geobuf",
    "geopy",
    "geographiclib",
    "google.protobuf",
    "clr",
    "pythonnet",
    "clr_loader",
    "webview",
    "webview.platforms.winforms",
    "webview.platforms.edgechromium",
]
hiddenimports += collect_submodules("uvicorn")

a = Analysis(
    ["desktop_app.py"],
    pathex=[".", "backend"],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "PIL", "scipy", "pandas", "pytest"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="HILTRON",
    icon="assets/hiltron.ico",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="HILTRON",
)

