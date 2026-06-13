"""Resolve the command an MCP client should run to start Daimon.

Prefer an installed `daimon` console script; fall back to `python -m daimon`
with the current interpreter so it works from a venv/source checkout too."""

from __future__ import annotations

import shutil
import sys


def daimon_command() -> dict:
    exe = shutil.which("daimon")
    if exe:
        return {"command": exe, "args": [], "env": {}}
    return {"command": sys.executable, "args": ["-m", "daimon"], "env": {}}
