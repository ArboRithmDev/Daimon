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

# NOTE: do NOT collect_all("PySide6"). That drags in EVERY Qt module
# (WebEngine, 3D, Charts, Bluetooth, …) — ~640 MB and minutes of analysis.
# PyInstaller's bundled PySide6 hook collects only the Qt modules actually
# imported (QtCore/QtGui/QtWidgets here). Same for numpy/cv2: their hooks fire
# when windows-capture imports them, so we don't sweep them wholesale either.
for pkg in (
    "comtypes",
    "uiautomation",
    "win32api",
    "win32gui",
    "win32con",
    "win32process",
    "mcp",
    "PIL",
    "yaml",
    # Face UI layer (pywebview EdgeChromium/WebView2). collect_all is guarded, so
    # a machine without these still builds a faceless-but-working exe.
    "webview",       # pywebview
    "clr_loader",    # pythonnet's CLR bootstrap
    "pythonnet",     # WinForms + WebView2 host via the CLR
    "bottle",        # pywebview's http_server (serves the bundle over 127.0.0.1)
    "daimon",
):
    try:
        datas, binaries, hidden = collect_all(pkg)
    except Exception:
        continue
    collected_datas.extend(datas)
    collected_binaries.extend(binaries)
    hidden_imports.extend(hidden)

# Heavy Qt modules we never use — exclude defensively so no transitive hint
# pulls them back in. (The hook already skips unimported modules; this pins it.)
_QT_EXCLUDES = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQml", "PySide6.QtCharts",
    "PySide6.QtDataVisualization", "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DExtras", "PySide6.QtPdf",
    "PySide6.QtPdfWidgets", "PySide6.QtBluetooth", "PySide6.QtPositioning",
    "PySide6.QtSensors", "PySide6.QtSerialPort", "PySide6.QtSql", "PySide6.QtTest",
    "PySide6.QtNetworkAuth", "PySide6.QtWebSockets", "PySide6.QtWebChannel",
    "PySide6.QtDesigner", "PySide6.QtHelp", "PySide6.QtUiTools",
]

# Brand assets — the tray glyph loaded by the status item. Ship the COLOURED
# Duo .svg (Windows tray, rendered via QtSvg) alongside the macOS template PNGs.
_assets = src_root / "daimon" / "assets"
if _assets.is_dir():
    for _pat in ("*.png", "*.svg"):
        for _f in _assets.glob(_pat):
            collected_datas.append((str(_f), "daimon/assets"))

# Face web bundle — the built offline UI (HTML/JS/CSS) the webviews load. Built
# by build/make_face.py before PyInstaller; ship dist/ so the frozen app serves
# it via face.host._dist_dir() (sys._MEIPASS when frozen). Harmless static files
# even before pywebview is wired as a Windows dependency.
_face_dist = src_root / "daimon" / "face" / "web" / "dist"
if _face_dist.is_dir():
    for _f in _face_dist.rglob("*"):
        if _f.is_file():
            _rel = Path("daimon/face/web/dist") / _f.relative_to(_face_dist).parent
            collected_datas.append((str(_f), str(_rel)))

# QtSvg is imported lazily (tray glyph + icon render); pin it so the PySide6 hook
# can't drop it from a static-analysis miss.
hidden_imports.append("PySide6.QtSvg")
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
    excludes=(["test", "tests", "pytest", "_pytest", "ruff", "setuptools",
               "cv2", "numpy", "windows_capture"]  # WGC path dropped (see screen_win)
              + _QT_EXCLUDES),
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Two executables, distinct names (no case-collision), sharing one payload:
#
#  * Daimon.exe     — WINDOWED. Double-click entry: the resident tray + onboarding.
#                     console=False so there is no console flash.
#  * daimon-mcp.exe — CONSOLE. What MCP clients spawn as `daimon-mcp.exe serve`.
#                     A GUI-subsystem exe does NOT work as an stdio MCP server for
#                     stricter clients (e.g. Antigravity/Gemini won't load it) — the
#                     server MUST be a console-subsystem process, like every other
#                     working MCP server. So the server gets its own console exe.
exe_gui = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Daimon",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=True,  # no crash dialog for the bg exe
    icon=icon_arg,
)

exe_mcp = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="daimon-mcp",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=True, disable_windowed_traceback=False,
    icon=icon_arg,
)

coll = COLLECT(
    exe_gui, exe_mcp,
    a.binaries, a.zipfiles, a.datas,
    strip=False, upx=False, upx_exclude=[],
    name="Daimon",
)
