"""PolicyGuard — the single chokepoint every action passes through.

Order of checks (any failure short-circuits):
  1. Level gate     — action.level must be ≤ the active ceiling.
  2. Exclusion gate — never act on a target inside a secrets zone.
  3. Reversibility  — Daimon's verdict vs the AI's declaration; stricter wins.
  4. Decision       — L4: ALLOW (flag destructive for mandatory logging);
                      L0–L3: GATE if any non-return signal, else ALLOW.
"""

from __future__ import annotations

from typing import Callable

from ..exclusions import ExclusionFilter
from . import reversibility
from .types import Decision, Level, MotorAction, Verdict


class PolicyGuard:
    def __init__(
        self,
        exclusions: ExclusionFilter,
        ceiling_provider: Callable[[], Level],
        classifier=reversibility.classify,
    ) -> None:
        self._exclusions = exclusions
        self._ceiling = ceiling_provider
        self._classify = classifier

    def evaluate(self, action: MotorAction) -> Decision:
        ceiling = self._ceiling()

        if action.level > ceiling:
            return Decision(Verdict.REFUSE, f"level {action.level.name} above ceiling {ceiling.name}")

        if self._exclusions.is_title_excluded(action.target.label):
            return Decision(Verdict.REFUSE, "target in exclusion zone")

        if not action.target.observed:
            if ceiling == Level.AUTONOMOUS:
                return Decision(Verdict.REFUSE, "target unobservable under L4 (no blind autonomous action)")
            return Decision(Verdict.GATE, "Daimon could not verify the target")

        rev = self._classify(action)
        risky = rev.irreversible or (action.declaration.reversible is False)

        if ceiling == Level.AUTONOMOUS:
            return Decision(Verdict.ALLOW, "L4 autonomous", must_log=risky)

        if risky:
            reason = rev.reason if rev.irreversible else "AI declared action irreversible"
            return Decision(Verdict.GATE, reason)

        return Decision(Verdict.ALLOW, "reversible, within ceiling")
