"""Resolve the command an MCP client should run to start Daimon.

Resolution order:
  1. the bundled binary inside an installed Daimon.app (after a DMG install),
  2. an installed `daimon` console script,
  3. `python -m daimon` with the current interpreter (venv/source checkout).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

_BUNDLE_DAIMON = Path("/Applications/Daimon.app/Contents/MacOS/daimon")


def daimon_command() -> dict:
    if _BUNDLE_DAIMON.exists():
        return {"command": str(_BUNDLE_DAIMON), "args": [], "env": {}}
    exe = shutil.which("daimon")
    if exe:
        return {"command": exe, "args": [], "env": {}}
    return {"command": sys.executable, "args": ["-m", "daimon"], "env": {}}
