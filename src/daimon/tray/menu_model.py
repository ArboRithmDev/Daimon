"""Pure declarative menu model. The AppKit layer renders these items and routes
their action_id; keeping the structure here makes the menu logic unit-testable
and Windows-portable."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..motor.types import Level
from .state import TrayState

# Ceilings the menu may set — L4 (AUTONOMOUS) is intentionally excluded: it
# requires written consent via the control CLI, never a menu click.
_SETTABLE_CEILINGS = (Level.READ, Level.NONDESTRUCTIVE, Level.INPUT, Level.VALIDATION)


@dataclass(frozen=True)
class MenuItem:
    kind: str                      # label|separator|action|radio|checkbox|submenu
    label: str = ""
    action_id: str = ""
    checked: bool = False
    enabled: bool = True
    children: tuple = field(default_factory=tuple)


def _dot(ok: bool) -> str:
    return "✅" if ok else "⚪"


def build_menu(state: TrayState) -> list[MenuItem]:
    ceiling_children = tuple(
        MenuItem(kind="radio", label=lvl.name, action_id=f"set_ceiling:{lvl.name}",
                 checked=(state.ceiling == lvl))
        for lvl in _SETTABLE_CEILINGS
    )
    clients_children = tuple(
        MenuItem(kind="label", label=f"{c.name}  {_dot(c.registered)}")
        for c in state.clients
    ) or (MenuItem(kind="label", label="No AI clients detected", enabled=False),)

    items: list[MenuItem] = [
        MenuItem(kind="label", label=f"Daimon v{state.version}", enabled=False),
        MenuItem(kind="separator"),
        MenuItem(kind="label", label=f"👁 Screen Recording  {_dot(state.screen_ok)}", enabled=False),
        MenuItem(kind="label", label=f"✋ Accessibility  {_dot(state.accessibility_ok)}", enabled=False),
        MenuItem(kind="submenu", label=f"Clients ({sum(c.registered for c in state.clients)})",
                 children=clients_children),
        MenuItem(kind="separator"),
        MenuItem(kind="submenu", label=f"Hands ceiling: {state.ceiling.name}",
                 children=ceiling_children),
        MenuItem(kind="checkbox", label="Show overlay", action_id="toggle_overlay",
                 checked=state.overlay_on),
    ]
    if state.l4_active:
        items.append(MenuItem(kind="label", label="⚠️ L4 AUTONOMY ACTIVE", enabled=False))
    items += [
        MenuItem(kind="separator"),
        MenuItem(kind="action", label="Run setup…", action_id="run_setup"),
        MenuItem(kind="action", label="Open config folder", action_id="open_config"),
        MenuItem(kind="action", label="Open logs", action_id="open_logs"),
        MenuItem(kind="separator"),
        MenuItem(kind="action", label="Quit Daimon", action_id="quit"),
    ]
    return items
