from daimon.motor.probe import FakeProber, observed_target_from_node
from daimon.motor.types import Declaration, Level, MotorAction, Target


def _act(name, params):
    return MotorAction(name=name, level=Level.INPUT, target=Target(),
                       declaration=Declaration(reversible=True, intent="x"), params=params)


def test_node_to_observed_target():
    t = observed_target_from_node({"role": "AXButton", "title": "Send", "value": None}, x=10, y=20)
    assert t.role == "AXButton" and t.label == "Send" and t.observed is True
    assert t.x == 10 and t.y == 20


def test_fake_prober_returns_preset():
    p = FakeProber(target=Target(role="AXButton", label="Send", observed=True))
    out = p.observe(_act("click", {"x": 1, "y": 2}))
    assert out.label == "Send"


def test_fake_prober_failure_is_unobserved():
    p = FakeProber(fail=True)
    assert p.observe(_act("click", {"x": 1, "y": 2})).observed is False
