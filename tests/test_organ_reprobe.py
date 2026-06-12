# tests/test_organ_reprobe.py
from daimon.config import ExclusionConfig
from daimon.exclusions import ExclusionFilter
from daimon.motor.actuator import FakeActuator
from daimon.motor.audit import AppendOnlyLedger
from daimon.motor.gate import FakeGate
from daimon.motor.guard import PolicyGuard
from daimon.motor.organ import MotorOrgan
from daimon.motor.probe import FakeProber
from daimon.motor.types import Declaration, Level, MotorAction, Target


def _organ(tmp_path, ceiling, observed, gate_answer=False, actuator=None):
    guard = PolicyGuard(ExclusionFilter(ExclusionConfig()), ceiling_provider=lambda: ceiling)
    return MotorOrgan(
        guard=guard, gate=FakeGate(answer=gate_answer),
        actuator=actuator or FakeActuator(),
        session_log=AppendOnlyLedger(tmp_path / "s.jsonl"), clock=lambda: "T",
        prober=FakeProber(target=observed),
    )


def _claimed(label):
    return MotorAction(name="click", level=Level.INPUT,
                       target=Target(role="AXButton", label=label),
                       declaration=Declaration(reversible=True, intent="x"),
                       params={"x": 1, "y": 1})


def test_ai_lies_label_but_observed_send_is_gated(tmp_path):
    # AI claims "Cancel"; the real element under the coords is "Send".
    act = FakeActuator()
    observed = Target(role="AXButton", label="Send", observed=True)
    organ = _organ(tmp_path, Level.VALIDATION, observed, gate_answer=False, actuator=act)
    out = organ.act(_claimed("Cancel"))
    assert out["status"] == "refused"   # gated, human denied
    assert act.executed == []


def test_probe_failure_refused_under_l4(tmp_path):
    from daimon.motor.probe import FakeProber
    guard = PolicyGuard(ExclusionFilter(ExclusionConfig()), ceiling_provider=lambda: Level.AUTONOMOUS)
    act = FakeActuator()
    organ = MotorOrgan(guard=guard, gate=FakeGate(), actuator=act,
                       session_log=AppendOnlyLedger(tmp_path / "s.jsonl"), clock=lambda: "T",
                       prober=FakeProber(fail=True))
    out = organ.act(_claimed("Anything"))
    assert out["status"] == "refused"
    assert act.executed == []


def test_observed_target_used_for_classification(tmp_path):
    act = FakeActuator()
    observed = Target(role="AXButton", label="Cancel", observed=True)
    organ = _organ(tmp_path, Level.INPUT, observed, actuator=act)
    out = organ.act(_claimed("Send"))  # AI claims scary, reality is benign
    assert out["status"] == "done"     # classified on observed "Cancel" → allowed
    assert act.executed[0].target.label == "Cancel"
