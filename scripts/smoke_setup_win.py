"""Live onboarding + tray smoke (Windows).

Onboarding window (closes on Done):
    .venv-win\\Scripts\\python.exe scripts/smoke_setup_win.py

Resident tray (menu-bar icon; right-click for the menu; "Quit Daimon" to exit):
    .venv-win\\Scripts\\python.exe -m daimon.tray.app
"""

from __future__ import annotations

from daimon.setup.gui.window_win import run


if __name__ == "__main__":
    raise SystemExit(run())
