"""Resolve the command an MCP client should run to start the Daimon server.

The server is always launched with an explicit `serve` argument so it never
depends on no-arg defaulting (which, inside the .app, shows the onboarding GUI).

Resolution order:
  1. a frozen build runs ITSELF: `<sys.executable> serve` (the running Daimon
     binary, wherever it lives — installed or a dist/ test build). Never `-m`:
     the frozen exe ignores it and would launch the tray instead of the server.
  2. the bundled binary from an installed Daimon (the .app on macOS, the
     Program Files install on Windows),
  3. an installed `daimon` console script,
  4. `python -m daimon` with the current interpreter (venv/source checkout).
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

# macOS: single bundled executable (GUI on no-arg, serves on `serve`).
_BUNDLE_DAIMON = Path("/Applications/Daimon.app/Contents/MacOS/Daimon")


def _bundled_windows() -> Path | None:
    """The console dispatcher inside an installed Windows bundle, if present."""
    candidates = []
    for env in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            candidates.append(Path(base) / "Daimon" / "Daimon.exe")
    return next((p for p in candidates if p.exists()), None)


def daimon_command() -> dict:
    """Resolve the command+args an MCP client runs to start `daimon serve`."""
    # A frozen build IS the dispatcher — run it directly with `serve`. This is the
    # currently-running exe (a dist/ test build or an installed one), so it works
    # before installation too. `-m` would be ignored by the frozen exe and land
    # in the tray branch (the same trap as the overlay spawn).
    if getattr(sys, "frozen", False):
        return {"command": sys.executable, "args": ["serve"], "env": {}}
    if sys.platform == "win32":
        win = _bundled_windows()
        if win is not None:
            return {"command": str(win), "args": ["serve"], "env": {}}
    elif _BUNDLE_DAIMON.exists():
        return {"command": str(_BUNDLE_DAIMON), "args": ["serve"], "env": {}}
    exe = shutil.which("daimon")
    if exe:
        return {"command": exe, "args": ["serve"], "env": {}}
    return {"command": sys.executable, "args": ["-m", "daimon", "serve"], "env": {}}
