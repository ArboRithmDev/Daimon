from daimon.config import ExclusionConfig
from daimon.exclusions import ExclusionFilter
from daimon.motor.actuator import FakeActuator
from daimon.motor.audit import AppendOnlyLedger
from daimon.motor.gate import FakeGate
from daimon.motor.guard import PolicyGuard
from daimon.motor.organ import MotorOrgan
from daimon.motor.types import Declaration, Level, MotorAction, Target


def _organ(tmp_path, ceiling, gate_answer=False, actuator=None):
    guard = PolicyGuard(ExclusionFilter(ExclusionConfig()), ceiling_provider=lambda: ceiling)
    return MotorOrgan(
        guard=guard,
        gate=FakeGate(answer=gate_answer),
        actuator=actuator or FakeActuator(),
        session_log=AppendOnlyLedger(tmp_path / "session.jsonl"),
        clock=lambda: "T",
    )


def _action(level, target, reversible=True, name="click"):
    return MotorAction(
        name=name, level=level, target=target,
        declaration=Declaration(reversible=reversible, intent="x"),
    )


def test_refused_action_is_not_executed(tmp_path):
    act = FakeActuator()
    organ = _organ(tmp_path, Level.READ, actuator=act)
    out = organ.act(_action(Level.INPUT, Target(label="ok")))
    assert out["status"] == "refused"
    assert act.executed == []


def test_allowed_action_executes(tmp_path):
    act = FakeActuator()
    organ = _organ(tmp_path, Level.INPUT, actuator=act)
    out = organ.act(_action(Level.INPUT, Target(role="AXButton", label="Cancel")))
    assert out["status"] == "done"
    assert act.executed[0].name == "click"


def test_gated_action_denied_by_human_is_not_executed(tmp_path):
    act = FakeActuator()
    organ = _organ(tmp_path, Level.VALIDATION, gate_answer=False, actuator=act)
    out = organ.act(_action(Level.INPUT, Target(role="AXButton", label="Send")))
    assert out["status"] == "refused"
    assert act.executed == []


def test_gated_action_approved_executes_and_logs(tmp_path):
    act = FakeActuator()
    organ = _organ(tmp_path, Level.VALIDATION, gate_answer=True, actuator=act)
    out = organ.act(_action(Level.INPUT, Target(role="AXButton", label="Send")))
    assert out["status"] == "done"
    assert act.executed[0].target.label == "Send"
    assert (tmp_path / "session.jsonl").exists()


def test_l4_destructive_no_log_means_no_act(tmp_path):
    # Session log path points at a directory → write fails → action refused.
    bad = tmp_path / "as_dir"
    bad.mkdir()
    guard = PolicyGuard(ExclusionFilter(ExclusionConfig()), ceiling_provider=lambda: Level.AUTONOMOUS)
    act = FakeActuator()
    organ = MotorOrgan(
        guard=guard, gate=FakeGate(), actuator=act,
        session_log=AppendOnlyLedger(bad), clock=lambda: "T",
    )
    out = organ.act(_action(Level.VALIDATION, Target(role="AXButton", label="Send"), reversible=False, name="press"))
    assert out["status"] == "refused"
    assert "no-log" in out["reason"]
    assert act.executed == []
