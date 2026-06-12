"""Shared value types for the motor organ. Pure data — no macOS imports."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class Level(IntEnum):
    """Authorization ladder. Each level includes the previous ones."""

    READ = 0           # nothing (pure perception)
    NONDESTRUCTIVE = 1  # scroll, focus, internal navigation
    INPUT = 2          # click, type, drag
    VALIDATION = 3     # engaging buttons (send/confirm/pay)
    AUTONOMOUS = 4     # carte blanche — no per-action gate, everything traced


class Verdict(IntEnum):
    REFUSE = 0
    GATE = 1   # requires human confirmation
    ALLOW = 2


@dataclass(frozen=True)
class Target:
    """The UI element an action aims at, as probed by Touché (or raw coords)."""

    role: str | None = None
    label: str | None = None   # title / description text
    value: str | None = None
    x: int | None = None
    y: int | None = None


@dataclass(frozen=True)
class Declaration:
    """What the AI client asserts about an action it requests."""

    reversible: bool
    intent: str


@dataclass(frozen=True)
class MotorAction:
    name: str                 # "click" | "type" | "drag" | "press" | "navigate"
    level: Level
    target: Target
    declaration: Declaration
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Reversibility:
    irreversible: bool
    reason: str


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    reason: str
    must_log: bool = False
