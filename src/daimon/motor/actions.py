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


ACTIONS: dict[str, ActionDef] = {
    "main_navigate": ActionDef("main_navigate", Level.NONDESTRUCTIVE, "scroll/focus/switch/navigate"),
    "main_click": ActionDef("main_click", Level.INPUT, "click an element or coordinate"),
    "main_type": ActionDef("main_type", Level.INPUT, "type text"),
    "main_drag": ActionDef("main_drag", Level.INPUT, "drag/trace"),
    "main_press": ActionDef("main_press", Level.VALIDATION, "activate an engaging button"),
    "main_key": ActionDef("main_key", Level.INPUT, "discrete key / chord"),
    "main_hover": ActionDef("main_hover", Level.NONDESTRUCTIVE, "move pointer only"),
    "main_activate": ActionDef("main_activate", Level.NONDESTRUCTIVE, "bring app/window frontmost"),
    "main_mouse_down": ActionDef("main_mouse_down", Level.AUTONOMOUS, "press and hold a mouse button"),
    "main_mouse_up": ActionDef("main_mouse_up", Level.AUTONOMOUS, "release a held mouse button"),
    "main_key_down": ActionDef("main_key_down", Level.AUTONOMOUS, "press and hold a key"),
    "main_key_up": ActionDef("main_key_up", Level.AUTONOMOUS, "release a held key"),
}


def level_for(tool_name: str) -> Level:
    """Look up the nominal authorization level for a tool verb."""
    return ACTIONS[tool_name].level
