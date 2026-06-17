"""The Windows updater script generation (pure string). Any platform."""

from pathlib import Path

from daimon.update.apply_win import build_updater_script


def test_updater_script_stops_processes_installs_and_relaunches():
    s = build_updater_script(
        installer=Path(r"C:\Temp\Daimon-0.0.8-setup.exe"),
        install_dir=Path(r"C:\Users\me\AppData\Local\Programs\Daimon"),
        self_path=Path(r"C:\Temp\daimon-update.ps1"),
    )
    # stops both the tray and the MCP server processes that lock the bundle
    assert "Get-Process Daimon, daimon-mcp" in s
    assert "Stop-Process -Force" in s
    # runs the installer silently
    assert r"C:\Temp\Daimon-0.0.8-setup.exe" in s
    assert "/VERYSILENT" in s and "/SUPPRESSMSGBOXES" in s
    # relaunches the new tray, then cleans itself up
    assert "Start-Process" in s and r"\Daimon\Daimon.exe" in s
    assert "Remove-Item" in s and "daimon-update.ps1" in s
