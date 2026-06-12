import pytest

from daimon.motor.actuator import FakeActuator
from daimon.motor.types import Declaration, Level, MotorAction, Target


def _action(name, params):
    return MotorAction(
        name=name, level=Level.INPUT, target=Target(x=5, y=6),
        declaration=Declaration(reversible=True, intent="x"), params=params,
    )


def test_fake_actuator_records_executed_action():
    act = FakeActuator()
    result = act.execute(_action("click", {"x": 5, "y": 6}))
    assert result["status"] == "executed"
    assert act.executed[0].name == "click"


def test_fake_actuator_can_simulate_failure():
    act = FakeActuator(fail=True)
    with pytest.raises(RuntimeError):
        act.execute(_action("type", {"text": "hi"}))
