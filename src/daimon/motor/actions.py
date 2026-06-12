"""The verbs the motor organ exposes, and their nominal authorization level.

Single source of truth for the tool→level mapping. The *target* may raise the
gate requirement above this nominal level (see reversibility), but never below.
"""

from __future__ import annotations

from dataclasses import dataclass

from .types import Level


@dataclass(frozen=True)
class ActionDef:
    tool_name: str
    level: Level
    gesture: str  # human-readable description


ACTIONS: dict[str, ActionDef] = {
    "main_navigate": ActionDef("main_navigate", Level.NONDESTRUCTIVE, "scroll/focus/switch/navigate"),
    "main_click": ActionDef("main_click", Level.INPUT, "click an element or coordinate"),
    "main_type": ActionDef("main_type", Level.INPUT, "type text"),
    "main_drag": ActionDef("main_drag", Level.INPUT, "drag/trace"),
    "main_press": ActionDef("main_press", Level.VALIDATION, "activate an engaging button"),
}


def level_for(tool_name: str) -> Level:
    return ACTIONS[tool_name].level
