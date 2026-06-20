from daimon.config import ExclusionConfig
from daimon.exclusions import ExclusionFilter
from daimon.motor.guard import PolicyGuard
from daimon.motor.types import Declaration, Decision, Level, MotorAction, Reversibility, Target, Verdict


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


def test_keyboard_action_not_gated_for_missing_observed_target():
    # A benign chord (cmd+M) with no observable target used to GATE; now it ALLOWs at L3.
    g = _guard(Level.VALIDATION)
    a = MotorAction(name="key", level=Level.INPUT, target=Target(observed=False),
                    declaration=Declaration(reversible=True, intent="test"),
                    params={"key": "m", "modifiers": ["cmd"]})
    assert g.evaluate(a).verdict == Verdict.ALLOW


def test_positional_click_still_gates_for_missing_observed_target():
    g = _guard(Level.VALIDATION)
    a = MotorAction(name="click", level=Level.INPUT, target=Target(x=10, y=10, observed=False),
                    declaration=Declaration(reversible=True, intent="test"),
                    params={})
    assert g.evaluate(a).verdict == Verdict.GATE


def test_dangerous_keyboard_combo_still_gates():
    # Force the classifier to mark the combo irreversible — the keyboard exemption must NOT
    # bypass combo classification.
    from daimon.motor.reversibility import Reversibility
    g = PolicyGuard(
        ExclusionFilter(ExclusionConfig()),
        ceiling_provider=lambda: Level.VALIDATION,
        classifier=lambda a: Reversibility(irreversible=True, reason="dangerous combo")
    )
    a = MotorAction(name="key", level=Level.INPUT, target=Target(observed=False),
                    declaration=Declaration(reversible=True, intent="test"),
                    params={"key": "q", "modifiers": ["cmd"]})
    assert g.evaluate(a).verdict == Verdict.GATE


def test_guard_exposes_current_ceiling():
    g = _guard(Level.INPUT)
    assert g.current_ceiling() == Level.INPUT
