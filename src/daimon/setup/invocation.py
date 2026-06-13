"""Resolve the command an MCP client should run to start the Daimon server.

The server is always launched with an explicit `serve` argument so it never
depends on no-arg defaulting (which, inside the .app, shows the onboarding GUI).

Resolution order:
  1. the bundled binary inside an installed Daimon.app (after a DMG install),
  2. an installed `daimon` console script,
  3. `python -m daimon` with the current interpreter (venv/source checkout).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

# Single bundled executable (the .app double-click entry is the same binary; it
# shows the GUI on no-arg and serves on `serve`).
_BUNDLE_DAIMON = Path("/Applications/Daimon.app/Contents/MacOS/Daimon")


def daimon_command() -> dict:
    if _BUNDLE_DAIMON.exists():
        return {"command": str(_BUNDLE_DAIMON), "args": ["serve"], "env": {}}
    exe = shutil.which("daimon")
    if exe:
        return {"command": exe, "args": ["serve"], "env": {}}
    return {"command": sys.executable, "args": ["-m", "daimon", "serve"], "env": {}}
