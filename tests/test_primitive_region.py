from daimon.config import ExclusionConfig, Rect
from daimon.exclusions import ExclusionFilter
from daimon.motor.guard import PolicyGuard
from daimon.motor.types import Declaration, Level, MotorAction, Target, Verdict


def test_mouse_down_in_excluded_region_refused_even_at_l4():
    g = PolicyGuard(ExclusionFilter(ExclusionConfig(regions=(Rect(0, 0, 100, 100),))),
                    ceiling_provider=lambda: Level.AUTONOMOUS)
    a = MotorAction(name="mouse_down", level=Level.AUTONOMOUS,
                    target=Target(x=50, y=50, observed=True),
                    declaration=Declaration(reversible=True, intent="i"), params={"x": 50, "y": 50})
    assert g.evaluate(a).verdict == Verdict.REFUSE
