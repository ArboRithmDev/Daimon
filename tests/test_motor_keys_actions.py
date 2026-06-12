from daimon.motor.actions import ACTIONS, level_for
from daimon.motor.actuator import FakeActuator
from daimon.motor.reversibility import classify
from daimon.motor.types import Declaration, Level, MotorAction, Target


def test_new_verbs_registered():
    assert level_for("main_key") == Level.INPUT
    assert level_for("main_activate") == Level.NONDESTRUCTIVE
    assert level_for("main_hover") == Level.NONDESTRUCTIVE


def _key(params):
    return MotorAction(name="key", level=Level.INPUT, target=Target(),
                       declaration=Declaration(reversible=True, intent="x"), params=params)


def test_dangerous_key_combo_classified_irreversible():
    a = _key({"key": "delete", "modifiers": ["cmd"], "keystr": "cmd+delete"})
    assert classify(a).irreversible


def test_plain_key_is_reversible():
    a = _key({"key": "tab", "modifiers": [], "keystr": "tab"})
    assert not classify(a).irreversible


def test_fake_actuator_runs_key_and_activate():
    act = FakeActuator()
    act.execute(MotorAction(name="key", level=Level.INPUT, target=Target(),
                            declaration=Declaration(reversible=True, intent="x"),
                            params={"key": "return", "modifiers": []}))
    act.execute(MotorAction(name="activate", level=Level.NONDESTRUCTIVE, target=Target(),
                            declaration=Declaration(reversible=True, intent="x"),
                            params={"bundle": "com.apple.TextEdit"}))
    assert [a.name for a in act.executed] == ["key", "activate"]
