from daimon.motor.types import (
    Level, Verdict, Target, Declaration, MotorAction, Reversibility, Decision,
)


def test_level_ordering():
    assert Level.READ < Level.NONDESTRUCTIVE < Level.INPUT < Level.VALIDATION < Level.AUTONOMOUS
    assert int(Level.AUTONOMOUS) == 4


def test_motor_action_construction():
    action = MotorAction(
        name="click",
        level=Level.INPUT,
        target=Target(role="AXButton", label="Send"),
        declaration=Declaration(reversible=False, intent="send the email"),
        params={"x": 10, "y": 20},
    )
    assert action.target.label == "Send"
    assert action.declaration.reversible is False
    assert action.params["x"] == 10


def test_decision_defaults():
    d = Decision(verdict=Verdict.ALLOW, reason="ok")
    assert d.must_log is False
    assert Reversibility(irreversible=True, reason="verb").irreversible is True
