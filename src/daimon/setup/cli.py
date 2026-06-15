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


def _targets(adapters, client_filter=None):
    """Detected adapters, optionally narrowed to a single --client NAME."""
    adapters = adapters if adapters is not None else default_adapters()
    result = detected(adapters)
    if client_filter is not None:
        result = [a for a in result if a.name.lower() == client_filter.lower()]
    return result


def _parse_client_filter(rest: list[str]) -> str | None:
    """Return the value of --client NAME from a remainder arg list, or None."""
    i = 0
    while i < len(rest):
        if rest[i] == "--client" and i + 1 < len(rest):
            return rest[i + 1]
        i += 1
    return None


def cmd_status(adapters, client_filter=None) -> int:
    """Print each detected client and whether Daimon is registered there."""
    targets = _targets(adapters, client_filter)
    if not targets:
        _print("  (no supported AI clients detected)")
        return 0
    for a in targets:
        r = base.status(a, "daimon")
        tag = f"{_OK}registered{_END}" if r.action == "present" else f"{_DIM}not registered{_END}"
        _print(f"  {a.name:16} {tag}  {_DIM}{a.config_path}{_END}")
    return 0


def cmd_install(adapters, client_filter=None) -> int:
    """Register Daimon into each detected client (idempotent, backed-up)."""
    targets = _targets(adapters, client_filter)
    if not targets:
        _print("  (no supported AI clients detected)")
        return 0
    entry = daimon_command()
    ts = _ts()
    for a in targets:
        r = base.install(a, "daimon", entry, ts=ts)
        _print(f"  {a.name:16} {r.action}  {_DIM}{r.detail}{_END}")
    return 0


def cmd_uninstall(adapters, client_filter=None) -> int:
    """Remove Daimon's entry from each detected client (reversible)."""
    targets = _targets(adapters, client_filter)
    if not targets:
        _print("  (no supported AI clients detected)")
        return 0
    ts = _ts()
    for a in targets:
        r = base.uninstall(a, "daimon", ts=ts)
        _print(f"  {a.name:16} {r.action}")
    return 0


def run_command(argv, *, adapters=None, backend=None, io=None) -> int:
    """Dispatch a `daimon` subcommand; backends injectable for testing."""
    if not argv:
        _print("Usage: daimon [setup|install|uninstall|status|onboard]")
        return 2
    cmd, rest = argv[0], argv[1:]
    client_filter = _parse_client_filter(rest)
    if cmd == "status":
        return cmd_status(adapters, client_filter)
    if cmd == "install":
        return cmd_install(adapters, client_filter)
    if cmd == "uninstall":
        return cmd_uninstall(adapters, client_filter)
    if cmd in ("onboard", "setup"):
        from .onboard_flow import run_onboarding
        rc = 0
        if cmd == "setup":
            rc = cmd_install(adapters, client_filter)
        return rc or run_onboarding(backend=backend, io=io)
    _print(f"Unknown command: {cmd}")
    return 2
