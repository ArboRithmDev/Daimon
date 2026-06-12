"""Live motor smoke — requires a human present. Targets a TextEdit sandbox.

Run with the ceiling set to INPUT (config/motor.yaml) and TextEdit frontmost.
Demonstrates: a reversible type (no gate) executes; a press on a 'Send'-like
button gates for human confirmation.

    python scripts/smoke_motor.py
"""

from __future__ import annotations

from daimon.motor.factory import build_organ
from daimon.motor.types import Declaration, MotorAction, Target


def main() -> int:
    organ = build_organ()

    typed = organ.act(MotorAction(
        name="type", level=2,  # INPUT
        target=Target(role="AXTextArea", label="document"),
        declaration=Declaration(reversible=True, intent="write a smoke note"),
        params={"text": "Daimon motor smoke ok\n"},
    ))
    print("type:", typed)

    gated = organ.act(MotorAction(
        name="press", level=3,  # VALIDATION
        target=Target(role="AXButton", label="Send"),
        declaration=Declaration(reversible=False, intent="pretend send"),
        params={"x": 100, "y": 100},
    ))
    print("press (should gate):", gated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
