"""Pure visual theme — maps a style/level to colour, corner radius, animation.

RGBA components are 0..1 floats (Core Animation / NSColor friendly). One
carefully-tuned premium palette; levels are colour-coded by escalation."""

from __future__ import annotations

STYLES: dict[str, dict] = {
    "default": {"rgba": (0.60, 0.64, 0.70, 0.90), "radius": 8, "duration": 0.25, "pulse": False},
    "L1":      {"rgba": (0.55, 0.60, 0.66, 0.85), "radius": 8, "duration": 0.25, "pulse": False},
    "L2":      {"rgba": (0.25, 0.55, 0.95, 0.95), "radius": 8, "duration": 0.22, "pulse": False},
    "L3":      {"rgba": (0.96, 0.70, 0.20, 0.97), "radius": 9, "duration": 0.20, "pulse": True},
    "L4":      {"rgba": (0.66, 0.28, 0.85, 0.98), "radius": 9, "duration": 0.18, "pulse": True},
    "gate":    {"rgba": (0.92, 0.23, 0.23, 1.00), "radius": 10, "duration": 0.16, "pulse": True},
}


def style_for(name: str) -> dict:
    """Resolve a style/level name to its visual spec, falling back to default."""
    return STYLES.get(name, STYLES["default"])
