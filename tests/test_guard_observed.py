from daimon.config import ExclusionConfig
from daimon.exclusions import ExclusionFilter
from daimon.motor.guard import PolicyGuard
from daimon.motor.types import Declaration, Level, MotorAction, Target, Verdict


def _guard(ceiling):
    return PolicyGuard(ExclusionFilter(ExclusionConfig()), ceiling_provider=lambda: ceiling)


def _act(level, target):
    return MotorAction(name="click", level=level, target=target,
                       declaration=Declaration(reversible=True, intent="x"), params={})


def test_unobserved_target_gates_below_l4():
    d = _guard(Level.VALIDATION).evaluate(_act(Level.INPUT, Target(observed=False)))
    assert d.verdict == Verdict.GATE


def test_unobserved_target_refused_under_l4():
    d = _guard(Level.AUTONOMOUS).evaluate(_act(Level.VALIDATION, Target(observed=False)))
    assert d.verdict == Verdict.REFUSE


def test_observed_target_unaffected():
    d = _guard(Level.INPUT).evaluate(_act(Level.INPUT, Target(role="AXButton", label="Cancel", observed=True)))
    assert d.verdict == Verdict.ALLOW
