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
    """The guard's ruling on an action."""

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
    observed: bool = True


@dataclass(frozen=True)
class Declaration:
    """What the AI client asserts about an action it requests."""

    reversible: bool
    intent: str


@dataclass(frozen=True)
class MotorAction:
    """One requested gesture: the verb, its level, target, and the AI's declaration."""

    name: str                 # "click" | "type" | "drag" | "press" | "navigate"
    level: Level
    target: Target
    declaration: Declaration
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Reversibility:
    """Daimon's own point-of-no-return verdict on an action's target."""

    irreversible: bool
    reason: str


@dataclass(frozen=True)
class Decision:
    """The guard's verdict plus whether the action must be logged before acting."""

    verdict: Verdict
    reason: str
    must_log: bool = False
