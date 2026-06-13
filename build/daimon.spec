# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Daimon.

Build (from the repo root):

    pyinstaller build/daimon.spec --clean --noconfirm

Produces a one-dir bundle and, on macOS, a `Daimon.app` whose:

* CFBundleExecutable = `Daimon` (the windowed onboarding GUI — what a user
  double-clicks: it registers Daimon into detected AI clients and guides the
  macOS permission grants).
* `Contents/MacOS/daimon` = the console dispatcher (no-arg → MCP stdio server,
  back-compat; subcommands → setup CLI). This is the command MCP clients run.

Two EXE targets share one Analysis so the heavy pyobjc/mcp/Pillow payload is
collected once. `build/macos/build_macos.sh` then signs, wraps in a DMG, and
notarizes.
"""

# pylint: disable=all
from PyInstaller.utils.hooks import collect_all, collect_submodules
import os
import sys
from pathlib import Path

block_cipher = None
project_root = Path(SPECPATH).resolve().parent
src_root = project_root / "src"

icon_path = project_root / "build" / "generated-icons" / "Daimon.icns"
icon_arg = str(icon_path) if icon_path.exists() else None

bundle_version = os.environ.get("DAIMON_VERSION", "0.0.0")
bundle_build_number = os.environ.get("DAIMON_BUILD_NUMBER", "0")
bundle_min_os = os.environ.get("DAIMON_MIN_OS", "11.0")
bundle_id = os.environ.get("DAIMON_BUNDLE_ID", "fr.arborithm.daimon")

hidden_imports: list[str] = []
collected_datas: list[tuple[str, str]] = []
collected_binaries: list[tuple[str, str]] = []

# pyobjc + mcp + imaging + config. collect_all sweeps data/binaries/hidden.
for pkg in (
    "objc",
    "Quartz",
    "AppKit",
    "Foundation",
    "CoreFoundation",
    "ApplicationServices",
    "PyObjCTools",
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

hidden_imports.extend(collect_submodules("daimon"))
# Explicit pyobjc bridges PyInstaller sometimes misses.
hidden_imports.extend([
    "objc", "Quartz", "AppKit", "Foundation", "CoreFoundation",
    "ApplicationServices", "PyObjCTools.AppHelper",
])

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

# ONE executable. The entry is daimon/__main__.py, which dispatches on argv:
#   no-arg (frozen .app double-click) → onboarding GUI
#   `serve`                           → MCP stdio server (what clients invoke)
#   setup subcommands                 → setup CLI
# PyInstaller does not cleanly support two executables in one .app bundle, so a
# single dispatching binary is both simpler and what actually works.
#
# console=False (windowed) → no Terminal on double-click. stdio still works when
# an MCP client spawns `Daimon serve` with inherited pipes.
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="Daimon",
    debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
    console=False, disable_windowed_traceback=False,
    target_arch=None, codesign_identity=None, entitlements_file=None,
    icon=icon_arg,
)

coll = COLLECT(
    exe,
    a.binaries, a.zipfiles, a.datas,
    strip=False, upx=False, upx_exclude=[],
    name="Daimon",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="Daimon.app",
        icon=icon_arg,
        bundle_identifier=bundle_id,
        info_plist={
            "CFBundleDevelopmentRegion": "en",
            "CFBundleDisplayName": "Daimon",
            "CFBundleExecutable": "Daimon",          # dispatcher: menu-bar tray on double-click, server on `serve`
            "CFBundleIdentifier": bundle_id,
            "CFBundleInfoDictionaryVersion": "6.0",
            "CFBundleName": "Daimon",
            "CFBundlePackageType": "APPL",
            "CFBundleShortVersionString": bundle_version,
            "CFBundleVersion": bundle_build_number,
            "LSMinimumSystemVersion": bundle_min_os,
            "NSHighResolutionCapable": True,
            "NSPrincipalClass": "NSApplication",
            "NSHumanReadableCopyright": "© Arborithm — MIT",
        },
    )
