"""MotorOrgan — ties the chokepoint to the world.

act(action):
  1. guard.evaluate → REFUSE / GATE / ALLOW
  2. GATE → ask the human; deny → refuse
  3. if the decision requires logging (gated, or L4-destructive), write the
     session log FIRST. no-log = no-act: a failed write refuses the action.
  4. execute via the actuator; best-effort log the result.
"""

from __future__ import annotations

from typing import Callable

from .actuator import Actuator
from .audit import AppendOnlyLedger
from .gate import HumanGate
from .guard import PolicyGuard
from .probe import Prober
from .types import MotorAction, Verdict
from ..overlay.presenter import NullPresenter


class MotorOrgan:
    """Wires the guard, gate, actuator, and ledger into one act() chokepoint."""

    def __init__(
        self,
        guard: PolicyGuard,
        gate: HumanGate,
        actuator: Actuator,
        session_log: AppendOnlyLedger,
        clock: Callable[[], str],
        prober: Prober,
        presenter=None,
    ) -> None:
        self._guard = guard
        self._gate = gate
        self._actuator = actuator
        self._log = session_log
        self._clock = clock
        self._prober = prober
        self._presenter = presenter or NullPresenter()

    def _record(self, action: MotorAction, phase: str, extra: dict) -> bool:
        try:
            self._log.append({
                "ts": self._clock(),
                "phase": phase,
                "action": action.name,
                "target": action.target.label or action.target.role,
                "intent": action.declaration.intent,
                "declared_reversible": action.declaration.reversible,
                **extra,
            })
            return True
        except (OSError, ValueError):
            return False

    def _present(self, method: str, *args) -> None:
        try:
            getattr(self._presenter, method)(*args)
        except Exception:
            pass  # presentation never affects the action

    def act(self, action: MotorAction) -> dict:
        """Run an action through guard → gate → log → execute; no-log = no-act."""
        claimed = action.target
        observed = self._prober.observe(action)
        from dataclasses import replace
        action = replace(action, target=observed)
        if (claimed.role, claimed.label) != (observed.role, observed.label):
            self._record(action, "divergence",
                         {"claimed_role": claimed.role, "claimed_label": claimed.label,
                          "observed_role": observed.role, "observed_label": observed.label})
        decision = self._guard.evaluate(action)

        self._present("present_intent", action, decision)
        if decision.verdict == Verdict.REFUSE:
            self._present("present_refused", action, decision.reason)
            return {"status": "refused", "reason": decision.reason}

        if decision.verdict == Verdict.GATE:
            self._present("present_gate", action)
            if not self._gate.confirm(action):
                self._record(action, "denied", {"reason": "human denied"})
                self._present("present_refused", action, "human denied")
                return {"status": "refused", "reason": "human denied"}
            must_log = True
        else:
            must_log = decision.must_log

        if must_log and not self._record(action, "authorized", {"reason": decision.reason}):
            self._present("present_refused", action, "no-log=no-act")
            return {"status": "refused", "reason": "no-log=no-act (audit write failed)"}

        result = self._actuator.execute(action)
        self._record(action, "executed", {"result": result})
        self._present("present_executed", action, result)
        return {"status": "done", "result": result}
