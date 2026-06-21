"""Renderer-agnostic action router. The AppKit menu and the webview face both
dispatch user intent through here, so the routing is testable and shared. The
router only knows a fixed allowlist of action_ids; it carries no effects of its
own — it calls the injected handlers, which own the side effects (and their own
gating, e.g. the L4 consent dialog lives behind engage_l4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    reason: str = ""


class ActionHandlers(Protocol):
    def set_ceiling(self, name: str) -> None: ...
    def toggle_overlay(self) -> None: ...
    def install_all(self) -> None: ...
    def toggle_client(self, name: str) -> None: ...
    def engage_l4(self) -> None: ...
    def disengage_l4(self) -> None: ...
    def run_setup(self) -> None: ...
    def open_config(self) -> None: ...
    def open_logs(self) -> None: ...
    def quit(self) -> None: ...
    # Onboarding permission gestures (optional — only the onboarding surface uses them).
    def grant_screen(self) -> None: ...
    def grant_accessibility(self) -> None: ...
    def settings_screen(self) -> None: ...
    def settings_accessibility(self) -> None: ...


# Ceilings the UI may set directly. AUTONOMOUS (L4) is intentionally absent — it
# is reached only via engage_l4 (native consent dialog + ledger).
_SETTABLE = {"READ", "NONDESTRUCTIVE", "INPUT", "VALIDATION"}
_SIMPLE = {
    "toggle_overlay", "install_all", "engage_l4", "disengage_l4",
    "run_setup", "open_config", "open_logs", "quit",
    "grant_screen", "grant_accessibility", "settings_screen", "settings_accessibility",
}


class ActionRouter:
    """Parse an action_id and call the matching handler. Returns an ActionResult;
    never raises for an unknown id (it refuses)."""

    def __init__(self, handlers: ActionHandlers) -> None:
        self._h = handlers

    def dispatch(self, action_id: str) -> ActionResult:
        if action_id.startswith("set_ceiling:"):
            name = action_id[len("set_ceiling:"):]
            if name == "AUTONOMOUS":
                return ActionResult(False, "L4 is consent-gated; use engage_l4")
            if name not in _SETTABLE:
                return ActionResult(False, f"unknown ceiling: {name}")
            self._h.set_ceiling(name)
            return ActionResult(True)
        if action_id.startswith("toggle_client:"):
            self._h.toggle_client(action_id[len("toggle_client:"):])
            return ActionResult(True)
        if action_id in _SIMPLE:
            getattr(self._h, action_id)()
            return ActionResult(True)
        return ActionResult(False, f"unknown action: {action_id}")
