"""W2 — Windows motor backends: selector wiring, gate fail-safe, prober. Win-only.

Deliberately avoids issuing real input (SendInput would act on the live
desktop). It checks the selector returns the Windows types, the gate's
confirm-decision logic (via an injected confirmer, no desktop switch), and the
prober's pure no-target branch. Real click/type/drag and the Secure-Desktop
dialog are validated by an interactive smoke, not here.
"""

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows-only backends")


def test_selector_returns_windows_backends():
    import daimon.backends as backends
    from daimon.motor.actuator_win import WindowsActuator
    from daimon.motor.gate_win import WindowsGate
    from daimon.motor.prober_win import WindowsProber
    assert isinstance(backends.build_actuator(), WindowsActuator)
    assert isinstance(backends.build_gate(), WindowsGate)
    assert isinstance(backends.build_prober(), WindowsProber)


def _action(name, **params):
    from daimon.motor.types import Declaration, MotorAction, Target, Level
    return MotorAction(
        name=name, level=Level.INPUT,
        target=Target(x=params.get("x"), y=params.get("y")),
        declaration=Declaration(reversible=True, intent="test"),
        params=params,
    )


def test_unknown_action_raises():
    from daimon.motor.actuator_win import WindowsActuator
    with pytest.raises(ValueError):
        WindowsActuator().execute(_action("bogus"))


def test_navigate_zero_scroll_is_a_safe_noop():
    # scroll_y=0 hits the guard and issues no SendInput — a side-effect-free path.
    from daimon.motor.actuator_win import WindowsActuator
    out = WindowsActuator().execute(_action("navigate", scroll_y=0))
    assert out == {"status": "executed", "action": "navigate"}


def test_gate_confirmer_decision_mapping():
    from daimon.motor.gate_win import WindowsGate
    seen = {}

    def yes(prompt, timeout):
        seen["prompt"] = prompt; seen["timeout"] = timeout
        return True

    assert WindowsGate(confirmer=yes).confirm(_action("press", x=1, y=2)) is True
    assert "press" in seen["prompt"]          # the pure format_prompt was used
    assert seen["timeout"] == 30
    assert WindowsGate(confirmer=lambda p, t: False).confirm(_action("press")) is False


def test_gate_is_fail_safe_on_error():
    from daimon.motor.gate_win import WindowsGate
    def boom(prompt, timeout):
        raise RuntimeError("dialog blew up")
    assert WindowsGate(confirmer=boom).confirm(_action("press")) is False


def test_prober_unobserved_without_coords():
    from daimon.motor.prober_win import WindowsProber
    # A coord action with no x/y must yield an unobserved Target (guard will gate).
    t = WindowsProber().observe(_action("click"))
    assert t.observed is False
