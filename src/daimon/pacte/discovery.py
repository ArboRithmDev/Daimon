"""Find a cooperating app's loopback endpoint via its discovery file. FS + validation only."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from .protocol import PROTOCOL_VERSION

_KEYS = ("port", "token", "pid", "app", "protocol_version")


def _alive(pid: int) -> bool:
    """Whether `pid` names a live process.

    A stale discovery file from an unclean kill carries a dead pid; rejecting it
    avoids connecting to a recycled port. `pid <= 0` carries no liveness info (e.g.
    a test double) → treated as live. The probe is POSIX-only: on Windows
    `os.kill(pid, 0)` is not a safe no-op, so liveness is skipped there.
    """
    if pid <= 0 or os.name != "posix":
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True  # PermissionError (owned by another user) or other → exists; stay permissive
    return True


@dataclass(frozen=True)
class Endpoint:
    """A discovered cooperative endpoint: where to connect and the token to present."""

    port: int
    token: str
    pid: int
    app: str
    protocol_version: str


def _load(path: Path) -> Endpoint | None:
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not all(k in rec for k in _KEYS) or rec["protocol_version"] != PROTOCOL_VERSION:
        return None
    if not _alive(int(rec["pid"])):
        return None
    return Endpoint(port=int(rec["port"]), token=str(rec["token"]), pid=int(rec["pid"]),
                    app=str(rec["app"]), protocol_version=str(rec["protocol_version"]))


def discover(cooperative_dir: Path) -> Endpoint | None:
    """Newest valid discovery file in `cooperative_dir` → Endpoint, else None."""
    cooperative_dir = Path(cooperative_dir)
    if not cooperative_dir.is_dir():
        return None
    files = sorted(cooperative_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for f in files:
        ep = _load(f)
        if ep is not None:
            return ep
    return None
