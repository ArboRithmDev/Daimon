"""Out-of-band human confirmation channel for points of no return.

The real gate is a native macOS modal dialog driven by `osascript`; a timeout
or any error resolves to DENY. The AI cannot drive the dialog or self-confirm.
`FakeGate` is the test double. `format_prompt` is pure and unit-tested.
"""

from __future__ import annotations

from typing import Protocol

from .types import MotorAction

_TIMEOUT_SECONDS = 30


def format_prompt(action: MotorAction) -> str:
    """Render the human-facing confirmation text for a point-of-no-return action."""
    t = action.target
    where = t.label or t.role or (f"({t.x},{t.y})" if t.x is not None else "unknown target")
    return (
        f"Daimon — l'IA veut: {action.name} sur « {where} ».\n"
        f"Intent: {action.declaration.intent}\n"
        f"Réversible (déclaré): {action.declaration.reversible}"
    )


class HumanGate(Protocol):
    """The out-of-band channel that asks a human to authorize an action."""

    def confirm(self, action: MotorAction) -> bool: ...


class FakeGate:
    """Test double: returns a preset answer and records calls."""

    def __init__(self, answer: bool = False) -> None:
        self._answer = answer
        self.calls: list[MotorAction] = []

    def confirm(self, action: MotorAction) -> bool:
        self.calls.append(action)
        return self._answer


class MacOSGate:
    """Native modal dialog via osascript. Timeout/error → DENY (fail-safe)."""

    def confirm(self, action: MotorAction) -> bool:
        """Ask the human via a native dialog; any timeout or error denies (fail-safe)."""
        import subprocess

        prompt = format_prompt(action).replace('"', "'")
        script = (
            f'display dialog "{prompt}" buttons {{"Refuser", "Autoriser"}} '
            f'default button "Refuser" with title "Daimon — Confirmation" '
            f'giving up after {_TIMEOUT_SECONDS}'
        )
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=_TIMEOUT_SECONDS + 5,
            )
        except (subprocess.SubprocessError, OSError):
            return False
        if result.returncode != 0:
            return False  # user cancelled or error
        return "Autoriser" in result.stdout and "gave up:true" not in result.stdout
