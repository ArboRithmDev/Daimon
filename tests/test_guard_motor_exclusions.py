# tests/test_guard_motor_exclusions.py
from daimon.config import ExclusionConfig, Rect
from daimon.exclusions import ExclusionFilter
from daimon.motor.guard import PolicyGuard
from daimon.motor.types import Declaration, Level, MotorAction, Target, Verdict


def _act(x, y):
    return MotorAction(name="click", level=Level.INPUT,
                       target=Target(role="AXButton", label="ok", x=x, y=y, observed=True),
                       declaration=Declaration(reversible=True, intent="i"),
                       params={"x": x, "y": y})


def test_action_in_excluded_region_refused():
    cfg = ExclusionConfig(regions=(Rect(0, 0, 100, 100),))
    g = PolicyGuard(ExclusionFilter(cfg), ceiling_provider=lambda: Level.INPUT)
    assert g.evaluate(_act(50, 50)).verdict == Verdict.REFUSE


def test_action_outside_region_allowed():
    cfg = ExclusionConfig(regions=(Rect(0, 0, 100, 100),))
    g = PolicyGuard(ExclusionFilter(cfg), ceiling_provider=lambda: Level.INPUT)
    assert g.evaluate(_act(500, 500)).verdict == Verdict.ALLOW
