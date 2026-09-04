# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the Linux desktop app.

One-folder, deliberately not --onefile: onnxruntime, opencv, and PyMuPDF push
the bundle past 400 MB, and onefile re-extracts all of that to a temp directory
on every launch, which is slow and can fill /tmp on restricted systems.
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files

ROOT = Path(SPECPATH)

datas = []
for optional in ("app/fonts", "app/assets"):
    directory = ROOT / optional
    if not directory.is_dir():
        continue
    for item in sorted(directory.iterdir()):
        if item.is_file() and item.suffix != ".optimized":
            datas.append((str(item), optional))

datas += collect_data_files("customtkinter")
datas += collect_data_files("tkinterdnd2")
datas += collect_data_files("babeldoc")

hiddenimports = [
    "peewee",
    "pdf2zh.doclayout",
    "pdf2zh.high_level",
    "pdf2zh.converter",
    "pdf2zh.translator",
    "pikepdf",
    "pikepdf._core",
]

analysis = Analysis(
    [str(ROOT / "app" / "gui.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "PyQt5",
        "PyQt6",
        "PySide2",
        "PySide6",
        "IPython",
        "pytest",
        "scipy",
        "pandas",
        "onnxruntime.transformers",
        "onnxruntime.tools",
        "onnxruntime.quantization",
    ],
    noarchive=False,
)

pyz = PYZ(analysis.pure)

exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="LayoutLingua",
    icon=str(ROOT / "app" / "assets" / "icon.png"),
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

collect = COLLECT(
    exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="LayoutLingua",
)
