"""macOS apply: swap Daimon.app via a detached shell updater.

Mirror of apply_win: a small script in TEMP waits for the tray to quit, replaces
/Applications/Daimon.app from the downloaded DMG (or .zip), relaunches it, and
self-deletes. MCP clients respawn the server from the new bundle on demand.

NOTE: validated on macOS by Ben (cannot be exercised from the Windows CI here).
The script generation is pure and unit-tested cross-platform.
"""

from __future__ import annotations

from pathlib import Path

_TEMPLATE = """\
#!/bin/sh
sleep {delay}
pkill -f 'Daimon.app/Contents/MacOS' 2>/dev/null || true
sleep 1
case "{asset}" in
  *.dmg)
    MNT=$(mktemp -d)
    hdiutil attach "{asset}" -nobrowse -mountpoint "$MNT" >/dev/null
    rm -rf "{app}"
    cp -R "$MNT/Daimon.app" "{app_parent}/"
    hdiutil detach "$MNT" >/dev/null
    ;;
  *)
    TMP=$(mktemp -d)
    /usr/bin/unzip -q "{asset}" -d "$TMP"
    rm -rf "{app}"
    cp -R "$TMP/Daimon.app" "{app_parent}/"
    ;;
esac
open "{app}"
rm -f "{self}"
"""


def _app_bundle(install_dir: Path) -> Path:
    """Resolve Daimon.app from the running binary dir (…/Daimon.app/Contents/MacOS)."""
    p = Path(install_dir)
    for parent in [p, *p.parents]:
        if parent.name == "Daimon.app":
            return parent
    return Path("/Applications/Daimon.app")


def build_updater_script(asset: Path, app: Path, self_path: Path, *, delay: float = 1.0) -> str:
    """The shell updater body: quit → swap .app → relaunch → self-delete."""
    return _TEMPLATE.format(
        delay=delay, asset=str(asset), app=str(app),
        app_parent=str(app.parent), self=str(self_path),
    )


def apply(asset: Path, install_dir: Path) -> None:
    """Launch the detached updater. The caller (tray) quits right after."""
    import os
    import subprocess
    import tempfile

    app = _app_bundle(install_dir)
    script = Path(tempfile.gettempdir()) / "daimon-update.sh"
    script.write_text(build_updater_script(asset, app, script), encoding="utf-8")
    os.chmod(script, 0o755)
    subprocess.Popen(["/bin/sh", str(script)], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
