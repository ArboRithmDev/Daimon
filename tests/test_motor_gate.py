from daimon.motor.gate import FakeGate, format_prompt
from daimon.motor.types import Declaration, Level, MotorAction, Target


def _action():
    return MotorAction(
        name="press", level=Level.VALIDATION,
        target=Target(role="AXButton", label="Send"),
        declaration=Declaration(reversible=False, intent="send the email"),
    )


def test_format_prompt_mentions_action_target_intent():
    msg = format_prompt(_action())
    assert "press" in msg
    assert "Send" in msg
    assert "send the email" in msg


def test_fake_gate_returns_preset_and_records():
    gate = FakeGate(answer=True)
    assert gate.confirm(_action()) is True
    assert len(gate.calls) == 1


def test_fake_gate_denies_by_default():
    assert FakeGate().confirm(_action()) is False
