"""Live motor smoke (Windows) — requires a human present. Targets Notepad.

Run with the ceiling at INPUT (config/motor.yaml) and an empty Notepad
frontmost. Demonstrates: a reversible type (no gate) executes via SendInput; a
press classified as a point of no return gates on the Secure Desktop.

    .venv-win\\Scripts\\python.exe scripts/smoke_motor_win.py

The press uses (x, y) = (200, 200): point it at a real button to see the
re-probe + gate. Move Notepad so nothing destructive sits under that point.
"""

from __future__ import annotations

from daimon.motor.factory import build_organ
from daimon.motor.types import Declaration, MotorAction, Target


def main() -> int:
    organ = build_organ()

    typed = organ.act(MotorAction(
        name="type", level=2,  # INPUT
        target=Target(role="Edit", label="document"),
        declaration=Declaration(reversible=True, intent="write a smoke note"),
        params={"text": "Daimon motor smoke ok\n"},
    ))
    print("type:", typed)

    gated = organ.act(MotorAction(
        name="press", level=3,  # VALIDATION
        target=Target(role="Button", label="Send"),
        declaration=Declaration(reversible=False, intent="pretend send"),
        params={"x": 200, "y": 200},
    ))
    print("press (should gate on the Secure Desktop):", gated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
