"""Pure serializer: the immutable TrayState -> the JSON contract the webview
renders. Presentational only — it carries no secrets and no perception content,
and it exposes the real L0-L4 ceiling (AUTONOMOUS is never 'settable')."""

from __future__ import annotations

from ..tray.state import TrayState

# Locked brand track (the chosen Claude Design "Duo beside" identity).
BRAND = {
    "style": "organic", "lead": "beside", "finish": "indigo",
    "presence": "#B66CFF", "companion": "#E8B23A",
}

# Settable from the UI; AUTONOMOUS (L4) is consent-gated, never here.
_SETTABLE = ["READ", "NONDESTRUCTIVE", "INPUT", "VALIDATION"]


def serialize(state: TrayState) -> dict:
    return {
        "version": state.version,
        "permissions": {
            "screen_recording": bool(state.screen_ok),
            "accessibility": bool(state.accessibility_ok),
        },
        "clients": [{"name": c.name, "registered": bool(c.registered)} for c in state.clients],
        "ceiling": {
            "current": state.ceiling.name,
            "settable": list(_SETTABLE),
            "l4_active": bool(state.l4_active),
        },
        "overlay_on": bool(state.overlay_on),
        "brand": BRAND,
    }
