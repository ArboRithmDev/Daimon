"""Resolve the *observed* target of a motor action via UI Automation (Windows).

The Windows twin of ``MacOSProber``: same contract, same logic, but reads the
element via ``capture.accessibility_win`` (UIA) instead of the macOS AX API. A
probe failure yields an unobserved Target so the guard gates/refuses rather than
acting blind.
"""

from __future__ import annotations

from .probe import _COORD_ACTIONS, _FOCUS_ACTIONS, observed_target_from_node
from .types import MotorAction, Target


class WindowsProber:
    def observe(self, action: MotorAction) -> Target:
        from ..capture import accessibility_win as ax
        try:
            if action.name == "drag":
                x, y = action.params["to_x"], action.params["to_y"]
                return observed_target_from_node(ax.element_at(x, y), x=x, y=y)
            if action.name in _COORD_ACTIONS:
                x = action.params.get("x"); y = action.params.get("y")
                if x is None or y is None:
                    return Target(observed=False)
                return observed_target_from_node(ax.element_at(x, y), x=x, y=y)
            if action.name in _FOCUS_ACTIONS:
                return observed_target_from_node(ax.focused_element())
        except Exception:
            return Target(observed=False)
        # navigate/activate: no specific target to verify
        return Target(observed=True)
