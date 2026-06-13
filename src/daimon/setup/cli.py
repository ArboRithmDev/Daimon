"""Premium CLI front-end: daimon install|uninstall|status|onboard|setup.

Thin over the pure core (registry + invocation + wizard + permissions). Backends
are injectable so the whole CLI is testable without touching real configs or
macOS."""

from __future__ import annotations

import sys

from .clients import base
from .clients.registry import default_adapters, detected
from .invocation import daimon_command

_OK = "\033[32m"; _WARN = "\033[33m"; _DIM = "\033[2m"; _END = "\033[0m"


def _ts() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _print(msg: str) -> None:
    print(msg)


def _targets(adapters):
    adapters = adapters if adapters is not None else default_adapters()
    return detected(adapters)


def cmd_status(adapters) -> int:
    for a in _targets(adapters):
        r = base.status(a, "daimon")
        tag = f"{_OK}registered{_END}" if r.action == "present" else f"{_DIM}not registered{_END}"
        _print(f"  {a.name:16} {tag}  {_DIM}{a.config_path}{_END}")
    return 0


def cmd_install(adapters) -> int:
    entry = daimon_command()
    ts = _ts()
    for a in _targets(adapters):
        r = base.install(a, "daimon", entry, ts=ts)
        _print(f"  {a.name:16} {r.action}  {_DIM}{r.detail}{_END}")
    return 0


def cmd_uninstall(adapters) -> int:
    ts = _ts()
    for a in _targets(adapters):
        r = base.uninstall(a, "daimon", ts=ts)
        _print(f"  {a.name:16} {r.action}")
    return 0


def run_command(argv, *, adapters=None, backend=None, io=None) -> int:
    if not argv:
        _print("Usage: daimon [setup|install|uninstall|status|onboard]")
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "status":
        return cmd_status(adapters)
    if cmd == "install":
        return cmd_install(adapters)
    if cmd == "uninstall":
        return cmd_uninstall(adapters)
    if cmd in ("onboard", "setup"):
        from .onboard_flow import run_onboarding
        rc = 0
        if cmd == "setup":
            rc = cmd_install(adapters)
        return rc or run_onboarding(backend=backend, io=io)
    _print(f"Unknown command: {cmd}")
    return 2
