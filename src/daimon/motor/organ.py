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
from .focus import FocusProbe, window_is_frontmost
from .gate import HumanGate
from .guard import PolicyGuard
from .probe import Prober
from .types import Declaration, MotorAction, Target, Verdict
from ..overlay.presenter import NullPresenter

# Positional gestures whose effect depends on the target window being frontmost.
_FOCUS_SENSITIVE = {"click", "press", "drag", "mouse_down", "type", "key"}


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
        focus_probe: FocusProbe | None = None,
    ) -> None:
        self._guard = guard
        self._gate = gate
        self._actuator = actuator
        self._log = session_log
        self._clock = clock
        self._prober = prober
        self._presenter = presenter or NullPresenter()
        self._focus = focus_probe

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

        focus = self._handle_focus(action)

        result = self._actuator.execute(action)
        self._record(action, "executed", {"result": result})
        self._present("present_executed", action, result)
        return {"status": "done", "result": result, **focus}

    def _handle_focus(self, action: MotorAction) -> dict:
        """Make focus observable before a positional gesture (F3).

        When the action declares a target `window`, compare it against the
        frontmost app. If the window isn't frontmost: with `ensure_focus`,
        activate it first (re-checking the effect); otherwise attach an explicit
        warning so a no-effect gesture never reads as success. No focus probe,
        or no declared window, leaves behaviour unchanged.
        """
        if self._focus is None or action.name not in _FOCUS_SENSITIVE:
            return {}
        window = action.params.get("window")
        if not window:
            return {}
        if window_is_frontmost(self._focus.frontmost(), window):
            return {}
        if not action.params.get("ensure_focus"):
            return {"focus_warning": True,
                    "focus_detail": "target window is not frontmost; the gesture may have no effect"}
        # ensure_focus: bring the target window forward, then re-check.
        self._activate_window(window)
        if window_is_frontmost(self._focus.frontmost(), window):
            return {"focused": True}
        return {"focused": True, "focus_warning": True,
                "focus_detail": "activated the target window but it is still not frontmost"}

    def _activate_window(self, window: dict) -> None:
        """Issue an internal activate gesture for `window` (NONDESTRUCTIVE)."""
        from .actions import level_for
        params = {k: v for k, v in window.items() if v is not None}
        activate = MotorAction(
            name="activate", level=level_for("main_activate"), target=Target(),
            declaration=Declaration(reversible=True, intent="auto-focus target window"),
            params=params,
        )
        self._actuator.execute(activate)
        self._record(activate, "executed", {"result": {"auto_focus": True}})
        note = getattr(self._focus, "note_activated", None)
        if note is not None:
            note(window)
