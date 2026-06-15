"""Live Secure-Desktop gate smoke (Windows) — requires a human present.

Validates the security-critical W2 piece in isolation: the confirmation runs on
a separate desktop, so an agent's SendInput on the Default desktop cannot reach
it. The screen will switch to the (black) Daimon gate desktop with a Yes/No box,
then switch back when you answer or after the 30s timeout (timeout => DENY).

    .venv-win\\Scripts\\python.exe scripts/smoke_gate_win.py

Optional advanced check: while the gate is up, have another process fire
SendInput — it must NOT be able to click Yes (it lands on the Default desktop).
"""

from __future__ import annotations

from daimon.motor.gate_win import WindowsGate
from daimon.motor.types import Declaration, MotorAction, Target


def main() -> int:
    action = MotorAction(
        name="press", level=3,  # VALIDATION
        target=Target(role="Button", label="Send", x=200, y=200),
        declaration=Declaration(reversible=False, intent="pretend send (gate smoke)"),
        params={"x": 200, "y": 200},
    )
    print("Switching to the Daimon gate desktop — answer the Yes/No box...")
    ok = WindowsGate().confirm(action)
    print("gate result:", "AUTHORIZED" if ok else "DENIED (or timed out)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
