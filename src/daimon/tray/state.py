"""Aggregated tray state + a thin reader that gathers it from the real sources."""

from __future__ import annotations

from dataclasses import dataclass

from ..motor.types import Level


@dataclass(frozen=True)
class ClientStatus:
    """Whether a detected AI client currently has Daimon registered into it."""

    name: str
    registered: bool


@dataclass(frozen=True)
class TrayState:
    """Immutable snapshot of everything the menu needs to render one frame."""

    version: str
    screen_ok: bool
    accessibility_ok: bool
    clients: tuple[ClientStatus, ...]
    ceiling: Level
    l4_active: bool
    overlay_on: bool


def gather() -> TrayState:
    """Read the real sources (config + permission marker + client registry).

    Thin and side-effecting (filesystem reads) — exercised by the live app, not
    unit tests, which construct TrayState directly.
    """
    from .. import __version__
    from ..config import load_motor_config, load_overlay_config
    from ..setup.clients.base import status as client_status
    from ..setup.clients.registry import default_adapters, detected
    from ..setup.permissions import read_status

    perms = read_status()
    motor = load_motor_config()
    overlay = load_overlay_config()
    clients = tuple(
        ClientStatus(a.name, client_status(a, "daimon").action == "present")
        for a in detected(default_adapters())
    )
    return TrayState(
        version=__version__,
        screen_ok=bool(perms.get("screen_recording")),
        accessibility_ok=bool(perms.get("accessibility")),
        clients=clients,
        ceiling=motor.ceiling,
        l4_active=False,  # L4 is runtime/consent-gated; shown read-only if engaged
        overlay_on=overlay.enabled,
    )
