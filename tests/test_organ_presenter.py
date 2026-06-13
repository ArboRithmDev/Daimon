# tests/test_organ_presenter.py
from daimon.config import ExclusionConfig
from daimon.exclusions import ExclusionFilter
from daimon.motor.actuator import FakeActuator
from daimon.motor.audit import AppendOnlyLedger
from daimon.motor.gate import FakeGate
from daimon.motor.guard import PolicyGuard
from daimon.motor.organ import MotorOrgan
from daimon.motor.probe import FakeProber
from daimon.overlay.presenter import RecordingPresenter
from daimon.motor.types import Declaration, Level, MotorAction, Target


def _organ(tmp_path, ceiling, observed, gate_answer=False, presenter=None):
    guard = PolicyGuard(ExclusionFilter(ExclusionConfig()), ceiling_provider=lambda: ceiling)
    return MotorOrgan(guard=guard, gate=FakeGate(answer=gate_answer), actuator=FakeActuator(),
                      session_log=AppendOnlyLedger(tmp_path / "s.jsonl"), clock=lambda: "T",
                      prober=FakeProber(target=observed), presenter=presenter)


def _act():
    return MotorAction(name="click", level=Level.INPUT, target=Target(role="AXButton", label="x"),
                       declaration=Declaration(reversible=True, intent="i"), params={"x": 1, "y": 1})


def test_allowed_action_presents_intent_then_executed(tmp_path):
    rp = RecordingPresenter()
    organ = _organ(tmp_path, Level.INPUT, Target(role="AXButton", label="Cancel", observed=True), presenter=rp)
    organ.act(_act())
    kinds = [c[0] for c in rp.calls]
    assert kinds[0] == "intent" and "executed" in kinds


def test_gated_denied_presents_gate_then_refused(tmp_path):
    rp = RecordingPresenter()
    organ = _organ(tmp_path, Level.VALIDATION, Target(role="AXButton", label="Send", observed=True),
                   gate_answer=False, presenter=rp)
    organ.act(_act())
    kinds = [c[0] for c in rp.calls]
    assert "gate" in kinds and "refused" in kinds


def test_presenter_receives_observed_target(tmp_path):
    rp = RecordingPresenter()
    observed = Target(role="AXButton", label="Send", observed=True)
    organ = _organ(tmp_path, Level.INPUT, observed, presenter=rp)
    organ.act(_act())  # action claims label "x"; presenter must see observed "Send"
    intent_action = next(a for k, a in rp.calls if k == "intent")
    assert intent_action.target.label == "Send"


def test_no_presenter_defaults_to_null(tmp_path):
    organ = _organ(tmp_path, Level.INPUT, Target(role="AXButton", label="Cancel", observed=True))
    assert organ.act(_act())["status"] == "done"  # works with default NullPresenter
