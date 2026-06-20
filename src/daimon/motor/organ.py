"""MotorOrgan — ties the chokepoint to the world.

act(action):
  1. guard.evaluate → REFUSE / GATE / ALLOW
  2. GATE → ask the human; deny → refuse
  3. if the decision requires logging (gated, or L4-destructive), write the
     session log FIRST. no-log = no-act: a failed write refuses the action.
  4. execute via the actuator; best-effort log the result.
"""

from __future__ import annotations

import time
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

# Window activation is asynchronous on the host: after an activate is issued the
# window server switches the frontmost app a few tens of ms later. We re-read the
# frontmost app up to _FOCUS_SETTLE_ATTEMPTS times, waiting _FOCUS_SETTLE_DELAY
# between reads, so a genuine activation is not misreported as "never came
# forward" merely because the switch had not landed at the first read.
_FOCUS_SETTLE_ATTEMPTS = 6
_FOCUS_SETTLE_DELAY = 0.03


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
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        self._guard = guard
        self._gate = gate
        self._actuator = actuator
        self._log = session_log
        self._clock = clock
        self._prober = prober
        self._presenter = presenter or NullPresenter()
        self._focus = focus_probe
        self._sleep = sleeper or time.sleep

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

        When the action declares a target ``window``, name the focus outcome
        under a ``focus`` key so a no-effect gesture never reads as success and
        a pilot can branch on the state instead of parsing warnings:

        - ``already_frontmost`` — the window was frontmost; nothing to do.
        - ``not_attempted`` — the window was not frontmost and ``ensure_focus``
          was off, so no activation was tried (carries a focus warning).
        - ``activated_and_frontmost`` — ``ensure_focus`` brought it forward.
        - ``activated_but_not_frontmost`` — an activate was issued but the
          window still did not come forward (carries a focus warning).

        No focus probe, a non-positional action, or no declared window leaves
        the result unchanged (no ``focus`` key) — focus is not applicable here.
        """
        if self._focus is None or action.name not in _FOCUS_SENSITIVE:
            return {}
        window = action.params.get("window")
        if not window:
            return {}
        if window_is_frontmost(self._focus.frontmost(), window):
            return {"focus": "already_frontmost"}
        if not action.params.get("ensure_focus"):
            return {"focus": "not_attempted", "focus_warning": True,
                    "focus_detail": "target window is not frontmost; the gesture may have no effect"}
        # ensure_focus: bring the target window forward, then re-check. Activation
        # is async, so settle/retry before classifying (avoids a false negative).
        self._activate_window(window)
        if self._await_frontmost(window):
            return {"focus": "activated_and_frontmost", "focused": True}
        return {"focus": "activated_but_not_frontmost", "focused": True, "focus_warning": True,
                "focus_detail": "activated the target window but it is still not frontmost"}

    def _await_frontmost(self, window: dict) -> bool:
        """Whether `window` becomes frontmost within the settle budget.

        The host activates windows asynchronously: reading the frontmost app once,
        immediately after issuing the activate, races the window server and yields
        a false negative. Poll a few times with a short delay so a genuine
        activation is observed; give up (return False) once the budget is spent.
        """
        for attempt in range(_FOCUS_SETTLE_ATTEMPTS):
            if window_is_frontmost(self._focus.frontmost(), window):
                return True
            if attempt < _FOCUS_SETTLE_ATTEMPTS - 1:
                self._sleep(_FOCUS_SETTLE_DELAY)
        return False

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

    def current_ceiling(self):
        """Expose the active ceiling for read-only reporting (e.g. main_ceiling)."""
        return self._guard.current_ceiling()
