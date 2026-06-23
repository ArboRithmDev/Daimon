"""User-writable data directory for Daimon's live config, state, and logs.

The repo/bundle is read-only once packaged, so the writable files (motor.yaml,
overlay.yaml, exclusions.yaml, motor.state.json, the audit logs) must live in a
per-user location shared between the tray, the onboarding GUI, and the MCP
servers — all of which run as separate processes from the same .app.

Default per OS: ``~/Library/Application Support/Daimon`` (macOS),
``%APPDATA%\\Daimon`` (Windows), ``$XDG_DATA_HOME/Daimon`` (Linux). Override with
$DAIMON_DATA_DIR (handy for tests and source-checkout dev). The committed
``config/*.example.yaml`` templates stay in the repo and are only ever read.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def data_dir() -> Path:
    """The per-user writable root for Daimon's config, state, and logs."""
    env = os.environ.get("DAIMON_DATA_DIR")
    if env:
        return Path(env).expanduser()
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or (Path.home() / "AppData" / "Roaming")
        return Path(base) / "Daimon"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Daimon"
    # Linux / other: XDG.
    base = os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share")
    return Path(base) / "Daimon"


def config_dir() -> Path:
    """Where the live (writable) config files live."""
    return data_dir() / "config"


def logs_dir() -> Path:
    """Where the audit and app logs are written."""
    return data_dir() / "logs"


def cooperative_dir() -> Path:
    """Fixed cross-app rendezvous where cooperating apps drop their --dev discovery files.

    Deliberately a stable, well-known path (~/.daimon/cooperative) rather than Daimon's
    platform-specific data_dir(): a cooperating app (e.g. Delta) must be able to find it
    without knowing Daimon's install location. $DAIMON_COOPERATIVE_DIR overrides it (tests).
    """
    env = os.environ.get("DAIMON_COOPERATIVE_DIR")
    root = Path(env).expanduser() if env else (Path.home() / ".daimon" / "cooperative")
    root.mkdir(parents=True, exist_ok=True)
    return root
