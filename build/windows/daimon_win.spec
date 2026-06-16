# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Daimon on Windows.

Build (from the repo root, inside the Windows venv):

    pyinstaller build/windows/daimon_win.spec --clean --noconfirm

Produces a one-dir bundle ``dist/Daimon`` with a single ``Daimon.exe`` (the
macOS spec uses one dispatcher too — and on Windows ``Daimon.exe`` / ``daimon.exe``
would case-collide on the case-insensitive filesystem). The entry is
``daimon/__main__.py``, which dispatches on argv:

* no-arg (double-click) → the resident system-tray app / onboarding window;
* ``serve`` → the stdio MCP server (what clients invoke as ``Daimon.exe serve``);
* setup subcommands → the setup CLI.

``console=False`` avoids a console window on double-click; stdio still works when
an MCP client spawns ``Daimon.exe serve`` with inherited pipes (same as macOS).

``build/windows/build_windows.ps1`` then (optionally) Authenticode-signs the exe
and wraps it in an Inno Setup installer.
"""

# pylint: disable=all
from PyInstaller.utils.hooks import collect_all, collect_submodules
import os
from pathlib import Path

block_cipher = None
project_root = Path(SPECPATH).resolve().parents[1]
src_root = project_root / "src"

icon_path = project_root / "build" / "generated-icons" / "Daimon.ico"
icon_arg = str(icon_path) if icon_path.exists() else None

hidden_imports: list[str] = []
collected_datas: list[tuple[str, str]] = []
collected_binaries: list[tuple[str, str]] = []

# Windows backends + mcp + imaging + config. collect_all sweeps
# data/binaries/hidden imports (PySide6 plugins, windows-capture's native lib,
# comtypes/uiautomation, numpy/cv2 pulled by windows-capture, pywin32).
for pkg in (
    "PySide6",
    "shiboken6",
    "comtypes",
    "uiautomation",
    "windows_capture",
    "numpy",
    "cv2",
    "win32api",
    "win32gui",
    "win32con",
    "win32process",
    "mcp",
    "PIL",
    "yaml",
    "daimon",
):
    try:
        datas, binaries, hidden = collect_all(pkg)
    except Exception:
        continue
    collected_datas.extend(datas)
    collected_binaries.extend(binaries)
    hidden_imports.extend(hidden)

# Brand assets — the tray glyph loaded by the status item.
_assets = src_root / "daimon" / "assets"
if _assets.is_dir():
    for _png in _assets.glob("*.png"):
        collected_datas.append((str(_png), "daimon/assets"))

hidden_imports.extend(collect_submodules("daimon"))

a = Analysis(
    [str(src_root / "daimon" / "__main__.py")],
    pathex=[str(src_root)],
    binaries=collected_binaries,
    datas=collected_datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["test", "tests", "pytest", "_pytest", "ruff", "setuptools"],
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Single windowed dispatcher (no console flash on double-click; stdio still works
# when an MCP client spawns `Daimon.exe serve` with inherited pipes).
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Daimon",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False,
    icon=icon_arg,
)

coll = COLLECT(
    exe,
    a.binaries, a.zipfiles, a.datas,
    strip=False, upx=False, upx_exclude=[],
    name="Daimon",
)
