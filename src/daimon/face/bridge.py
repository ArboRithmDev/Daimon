"""The single typed JS<->Python surface exposed to the webview (pywebview js_api).
Exactly two methods: get_state (read serialized, non-secret view) and invoke
(route a known action_id through the shared ActionRouter). The web layer holds no
authority; this bridge cannot raise the ceiling and never returns secrets."""

from __future__ import annotations

from typing import Callable

from ..tray.actions import ActionRouter
from ..tray.state import TrayState
from .view_model import serialize


class FaceBridge:
    """js_api for the webview. `state_provider` reads a fresh TrayState (e.g.
    `daimon.tray.state.gather`); `router` is an ActionRouter over the real
    handlers (the same the AppKit menu uses)."""

    def __init__(self, router: ActionRouter, state_provider: Callable[[], TrayState]) -> None:
        self._router = router
        self._state = state_provider
        self._resizer: Callable[[int, int], None] | None = None

    def set_resizer(self, resizer: Callable[[int, int], None]) -> None:
        """Wire a window resizer (host-side) so the JS can fit the window to its
        content. Pure window mechanics — no authority, no state."""
        self._resizer = resizer

    def get_state(self) -> dict:
        return serialize(self._state())

    def invoke(self, action_id: str, args: dict | None = None) -> dict:
        res = self._router.dispatch(action_id)
        return {"ok": res.ok, "reason": res.reason}

    def resize_to(self, width: int, height: int) -> dict:
        if self._resizer is not None:
            self._resizer(int(width), int(height))
        return {"ok": True}
