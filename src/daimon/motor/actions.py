"""The verbs the motor organ exposes, and their nominal authorization level.

Single source of truth for the tool→level mapping. The *target* may raise the
gate requirement above this nominal level (see reversibility), but never below.
"""

from __future__ import annotations

from dataclasses import dataclass

from .types import Level


@dataclass(frozen=True)
class ActionDef:
    """Maps an exposed tool verb to its nominal authorization level."""

    tool_name: str
    level: Level
    gesture: str  # human-readable description
    requires_observed_target: bool = True  # False for acts with no screen target to verify


ACTIONS: dict[str, ActionDef] = {
    "main_navigate": ActionDef("main_navigate", Level.NONDESTRUCTIVE, "scroll/focus/switch/navigate", requires_observed_target=False),
    "main_click": ActionDef("main_click", Level.INPUT, "click an element or coordinate"),
    "main_type": ActionDef("main_type", Level.INPUT, "type text", requires_observed_target=False),
    "main_drag": ActionDef("main_drag", Level.INPUT, "drag/trace"),
    "main_press": ActionDef("main_press", Level.VALIDATION, "activate an engaging button"),
    "main_key": ActionDef("main_key", Level.INPUT, "discrete key / chord", requires_observed_target=False),
    "main_hover": ActionDef("main_hover", Level.NONDESTRUCTIVE, "move pointer only", requires_observed_target=False),
    "main_activate": ActionDef("main_activate", Level.NONDESTRUCTIVE, "bring app/window frontmost", requires_observed_target=False),
    "main_mouse_down": ActionDef("main_mouse_down", Level.AUTONOMOUS, "press and hold a mouse button"),
    "main_mouse_up": ActionDef("main_mouse_up", Level.AUTONOMOUS, "release a held mouse button"),
    "main_key_down": ActionDef("main_key_down", Level.AUTONOMOUS, "press and hold a key", requires_observed_target=False),
    "main_key_up": ActionDef("main_key_up", Level.AUTONOMOUS, "release a held key", requires_observed_target=False),
}


def level_for(tool_name: str) -> Level:
    """Look up the nominal authorization level for a tool verb."""
    return ACTIONS[tool_name].level


def requires_observed_target(action_name: str) -> bool:
    """Whether the SHORT-named action commits on a screen target that must be verified.

    True (default) for positional commits (click/press/drag/mouse_*); False for keyboard,
    window-by-bundle, and pure pointer moves, which carry no target to observe.
    """
    spec = ACTIONS.get("main_" + action_name)
    return spec.requires_observed_target if spec else True
