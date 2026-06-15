"""Resolve the command an MCP client should run to start the Daimon server.

The server is always launched with an explicit `serve` argument so it never
depends on no-arg defaulting (which, inside the .app, shows the onboarding GUI).

Resolution order:
  1. the bundled binary from an installed Daimon (the .app on macOS, the
     Program Files install on Windows),
  2. an installed `daimon` console script,
  3. `python -m daimon` with the current interpreter (venv/source checkout).
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
            candidates.append(Path(base) / "Daimon" / "daimon.exe")
    return next((p for p in candidates if p.exists()), None)


def daimon_command() -> dict:
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
