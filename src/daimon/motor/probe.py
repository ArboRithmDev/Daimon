"""Resolve the *observed* target of a motor action via Accessibility.

The AI's declared role/label are advisory; the guard must classify on what is
actually under the action's coordinates (or the focused element for keyboard
actions). A probe failure yields an unobserved Target so the guard can gate
(L0-L3) or refuse (L4) rather than act blind.
"""

from __future__ import annotations

from typing import Protocol

from .types import MotorAction, Target

# Actions whose target must be verified before acting.
_COORD_ACTIONS = {"click", "press", "drag", "hover", "mouse_down", "mouse_up"}
_FOCUS_ACTIONS = {"type", "key"}


def observed_target_from_node(node: dict, *, x=None, y=None) -> Target:
    return Target(
        role=node.get("role"), label=node.get("title") or node.get("description"),
        value=node.get("value"), x=x, y=y, observed=True,
    )


class Prober(Protocol):
    def observe(self, action: MotorAction) -> Target: ...


class FakeProber:
    def __init__(self, target: Target | None = None, fail: bool = False):
        self._target = target or Target(observed=True)
        self._fail = fail

    def observe(self, action: MotorAction) -> Target:
        if self._fail:
            return Target(observed=False)
        return self._target


class MacOSProber:
    """Real prober using capture.accessibility."""

    def observe(self, action: MotorAction) -> Target:
        from ..capture import accessibility as ax
        try:
            if action.name == "drag":
                # the drop destination is what matters for non-return
                x, y = action.params["to_x"], action.params["to_y"]
                return observed_target_from_node(ax.element_at(x, y), x=x, y=y)
            if action.name in _COORD_ACTIONS:
                x = action.params.get("x"); y = action.params.get("y")
                if x is None or y is None:
                    return Target(observed=False)
                return observed_target_from_node(ax.element_at(x, y), x=x, y=y)
            if action.name in _FOCUS_ACTIONS:
                node = ax.focused_element()
                return observed_target_from_node(node)
        except Exception:
            return Target(observed=False)
        # navigate/activate: no specific target to verify
        return Target(observed=True)
