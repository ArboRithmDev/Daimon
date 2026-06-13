"""Presenter — turns motor lifecycle events into overlay commands.

`Presenter` is the injected interface the MotorOrgan calls; `NullPresenter` is
the headless default (keeps the core testable). `OverlayPresenter` maps each
lifecycle point to protocol commands, applying the SAME secret redaction as the
senses so the overlay never displays protected content. Commands go to a `sink`
with a `.send(command)` method (the OverlayClient, or a recorder in tests).
"""

from __future__ import annotations

from typing import Protocol

from ..exclusions import ExclusionFilter
from ..motor.types import Decision, Level, MotorAction
from .protocol import Banner, Clear, Highlight, Ripple

_LEVEL_STYLE = {Level.NONDESTRUCTIVE: "L1", Level.INPUT: "L2",
                Level.VALIDATION: "L3", Level.AUTONOMOUS: "L2"}


class Presenter(Protocol):
    def present_intent(self, action: MotorAction, decision: Decision) -> None: ...
    def present_gate(self, action: MotorAction) -> None: ...
    def present_executed(self, action: MotorAction, result: dict) -> None: ...
    def present_refused(self, action: MotorAction, reason: str) -> None: ...


class NullPresenter:
    def present_intent(self, action, decision): pass
    def present_gate(self, action): pass
    def present_executed(self, action, result): pass
    def present_refused(self, action, reason): pass


class RecordingPresenter:
    """Test double recording which lifecycle points fired."""
    def __init__(self): self.calls = []
    def present_intent(self, action, decision): self.calls.append(("intent", action))
    def present_gate(self, action): self.calls.append(("gate", action))
    def present_executed(self, action, result): self.calls.append(("executed", action))
    def present_refused(self, action, reason): self.calls.append(("refused", action))


class OverlayPresenter:
    def __init__(self, sink, exclusions: ExclusionFilter) -> None:
        self._sink = sink
        self._exclusions = exclusions

    def _label(self, action: MotorAction) -> str:
        t = action.target
        if self._exclusions.is_target_secret(role=t.role):
            return "🔒 protégé"
        name = t.label or t.role or ""
        return f'{t.role or ""} "{name}"'.strip() if name else (t.role or "target")

    def _rect(self, action: MotorAction):
        t = action.target
        x = t.x if t.x is not None else 0
        y = t.y if t.y is not None else 0
        return x, y

    def _send(self, command) -> None:
        try:
            self._sink.send(command)
        except Exception:
            pass  # overlay is never on the critical path

    def present_intent(self, action, decision) -> None:
        x, y = self._rect(action)
        style = _LEVEL_STYLE.get(action.level, "default")
        self._send(Highlight(x=x - 24, y=y - 16, w=48, h=32, label=self._label(action), style=style))
        self._send(Banner(text=f"{action.name} • {action.declaration.intent}", level=style))

    def present_gate(self, action) -> None:
        x, y = self._rect(action)
        self._send(Highlight(x=x - 24, y=y - 16, w=48, h=32, label=self._label(action), style="gate"))
        self._send(Banner(text=f"CONFIRM • {action.name} • {self._label(action)}", level="L3"))

    def present_executed(self, action, result) -> None:
        x, y = self._rect(action)
        self._send(Ripple(x=x, y=y))

    def present_refused(self, action, reason) -> None:
        self._send(Banner(text=f"refused • {reason}", level="L1"))
        self._send(Clear())
