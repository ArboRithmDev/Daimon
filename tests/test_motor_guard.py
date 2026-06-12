from daimon.config import ExclusionConfig
from daimon.exclusions import ExclusionFilter
from daimon.motor.guard import PolicyGuard
from daimon.motor.types import Declaration, Decision, Level, MotorAction, Target, Verdict


def _guard(ceiling, exclusions=None):
    excl = ExclusionFilter(exclusions or ExclusionConfig())
    return PolicyGuard(exclusions=excl, ceiling_provider=lambda: ceiling)


def _action(level, target, reversible=True, name="click", params=None):
    return MotorAction(
        name=name, level=level, target=target,
        declaration=Declaration(reversible=reversible, intent="x"),
        params=params or {},
    )


def test_level_above_ceiling_is_refused():
    d = _guard(Level.NONDESTRUCTIVE).evaluate(_action(Level.INPUT, Target(label="ok")))
    assert d.verdict == Verdict.REFUSE


def test_reversible_within_ceiling_is_allowed():
    d = _guard(Level.INPUT).evaluate(_action(Level.INPUT, Target(role="AXButton", label="Cancel")))
    assert d.verdict == Verdict.ALLOW


def test_non_return_target_is_gated():
    d = _guard(Level.VALIDATION).evaluate(
        _action(Level.INPUT, Target(role="AXButton", label="Send"), reversible=True)
    )
    assert d.verdict == Verdict.GATE


def test_ai_declares_irreversible_forces_gate():
    d = _guard(Level.INPUT).evaluate(
        _action(Level.INPUT, Target(role="AXButton", label="Cancel"), reversible=False)
    )
    assert d.verdict == Verdict.GATE


def test_target_in_exclusion_zone_is_refused():
    d = _guard(Level.INPUT, ExclusionConfig(window_titles=(r"(?i)password",))).evaluate(
        _action(Level.INPUT, Target(role="AXTextField", label="Password field"))
    )
    assert d.verdict == Verdict.REFUSE


def test_l4_allows_without_gate_but_flags_log():
    d = _guard(Level.AUTONOMOUS).evaluate(
        _action(Level.VALIDATION, Target(role="AXButton", label="Send"), name="press")
    )
    assert d.verdict == Verdict.ALLOW
    assert d.must_log is True


def test_l4_reversible_action_allows_without_mandatory_log():
    d = _guard(Level.AUTONOMOUS).evaluate(
        _action(Level.INPUT, Target(role="AXButton", label="Cancel"))
    )
    assert d.verdict == Verdict.ALLOW
    assert d.must_log is False
