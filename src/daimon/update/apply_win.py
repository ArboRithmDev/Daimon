"""Windows apply: a detached PowerShell updater.

The running daimon-mcp.exe processes (spawned by MCP clients) lock the bundle, so
it cannot be overwritten in place. A small PowerShell script — living in TEMP,
not in the install dir, so it never locks what it replaces — waits for the tray
to exit, stops every Daimon process, runs the silent installer, and relaunches
the tray. MCP clients respawn daimon-mcp.exe on demand against the new bundle.
"""

from __future__ import annotations

from pathlib import Path

_DETACHED_PROCESS = 0x00000008
_CREATE_NEW_PROCESS_GROUP = 0x00000200
_CREATE_NO_WINDOW = 0x08000000

_TEMPLATE = """\
Start-Sleep -Milliseconds {delay}
Get-Process Daimon, daimon-mcp -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 600
& "{installer}" /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
Start-Process "{exe}"
Remove-Item -LiteralPath "{self}" -Force -ErrorAction SilentlyContinue
"""


def build_updater_script(installer: Path, install_dir: Path, self_path: Path,
                         *, delay_ms: int = 900) -> str:
    """The PowerShell updater body: stop processes → silent install → relaunch."""
    return _TEMPLATE.format(
        delay=delay_ms,
        installer=str(installer),
        exe=str(Path(install_dir) / "Daimon.exe"),
        self=str(self_path),
    )


def apply(installer: Path, install_dir: Path, *, delay_ms: int = 900) -> None:
    """Launch the detached updater. The caller (tray) must quit right after so its
    files unlock and the installer can replace them."""
    import subprocess
    import tempfile

    script = Path(tempfile.gettempdir()) / "daimon-update.ps1"
    script.write_text(build_updater_script(installer, install_dir, script, delay_ms=delay_ms),
                      encoding="utf-8")
    subprocess.Popen(
        ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
         "-WindowStyle", "Hidden", "-File", str(script)],
        creationflags=_DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP | _CREATE_NO_WINDOW,
    )
