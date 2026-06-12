"""Touché — sense #2. The hand that feels, never the hand that acts.

Two granularities of the *same* sense, both read-only:

  - touche_tree   (passif): accessibility-tree snapshot of the frontmost
                   window — for general structural understanding.
  - touche_probe  (actif):  the element under a screen point — "what is here?" —
                   so the eyes can guide the (separate, future) hands before
                   they act.

Both go through the same exclusion filter as Vue (redact_nodes / title gate).
Needs Accessibility permission; if it is missing the tools return a clear,
actionable message instead of crashing.
"""

from __future__ import annotations

from ..capture import accessibility as ax
from .base import Sense

_PERMISSION_HINT = (
    "Daimon lacks Accessibility permission. Grant it in System Settings → "
    "Privacy & Security → Accessibility for the process running `python -m daimon`."
)


class Touche(Sense):
    name = "touche"

    def register(self, mcp) -> None:
        @mcp.tool(
            name="touche_tree",
            description=(
                "Touché passif: accessibility tree of the frontmost window for "
                "structural understanding. Read-only. Returns nested nodes "
                "{role, title, value, position, size, children}."
            ),
        )
        def touche_tree() -> dict:
            if not ax.is_trusted():
                return {"error": "accessibility_permission_denied", "hint": _PERMISSION_HINT}
            tree = ax.snapshot_tree()
            return self._exclusions.redact_nodes([tree])[0]

        @mcp.tool(
            name="touche_probe",
            description=(
                "Touché actif: the accessibility element at screen point (x, y) — "
                "'what is here?'. Returns element info, never acts. Use to aim "
                "before the (separate) hands move."
            ),
        )
        def touche_probe(x: int, y: int) -> dict:
            if not ax.is_trusted():
                return {"error": "accessibility_permission_denied", "hint": _PERMISSION_HINT}
            node = ax.element_at(x, y)
            kept = self._exclusions.redact_nodes([node])
            if not kept:
                return {"error": "excluded", "hint": "Element falls under an exclusion zone."}
            return kept[0]
