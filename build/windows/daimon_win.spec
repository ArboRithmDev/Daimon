# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Daimon on Windows.

Build (from the repo root, inside the Windows venv):

    pyinstaller build/windows/daimon_win.spec --clean --noconfirm

Produces a one-dir bundle ``dist/Daimon`` with two executables sharing one
Analysis (the heavy PySide6/UIA/WGC payload is collected once):

* ``Daimon.exe``  — windowed (no console). The double-click entry: the resident
  system-tray app (and the onboarding window). This is what the Start-menu /
  installer shortcut points at.
* ``daimon.exe``  — console. The dispatcher MCP clients invoke as ``daimon serve``
  (stdio MCP server); subcommands run the setup CLI. Console subsystem so stdio
  is clean for the client pipe.

``build/windows/build_windows.ps1`` then (optionally) Authenticode-signs the
exes and wraps them in an Inno Setup installer.
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

# Windowed entry (no console) — the tray / onboarding GUI on double-click.
exe_gui = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Daimon",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False,
    icon=icon_arg,
)

# Console entry — what MCP clients launch as `daimon serve`.
exe_cli = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="daimon",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=True, disable_windowed_traceback=False,
    icon=icon_arg,
)

coll = COLLECT(
    exe_gui, exe_cli,
    a.binaries, a.zipfiles, a.datas,
    strip=False, upx=False, upx_exclude=[],
    name="Daimon",
)
