from daimon.motor.audit import AppendOnlyLedger
from daimon.motor.types import Level, MotorAction, Target, Declaration
from daimon.pacte.session import CooperativeSession, DEFAULT_SESSION_CEILING
from daimon.pacte.gate import CooperativeGate


def _ledger(tmp_path):
    return AppendOnlyLedger(tmp_path / "c.jsonl")


def _action(level):
    return MotorAction(name="drag", level=level, target=Target(observed=True),
                       declaration=Declaration(reversible=True, intent="t"))


def test_closed_session_has_read_ceiling(tmp_path):
    s = CooperativeSession(_ledger(tmp_path), clock=lambda: "ts")
    assert s.active() is False
    assert s.ceiling() == Level.READ


def test_open_records_one_entry_and_raises_ceiling(tmp_path):
    led = _ledger(tmp_path)
    s = CooperativeSession(led, clock=lambda: "ts")
    s.open(app="delta", pid=42)
    assert s.active() is True
    assert s.ceiling() == DEFAULT_SESSION_CEILING
    recs = led._records()
    assert recs[-1]["event"] == "cooperative_open" and recs[-1]["app"] == "delta"


def test_ceiling_clamped_below_autonomous(tmp_path):
    s = CooperativeSession(_ledger(tmp_path), clock=lambda: "ts", ceiling=Level.AUTONOMOUS)
    s.open(app="delta", pid=1)
    assert s.ceiling() == Level.VALIDATION


def test_gate_confirms_within_ceiling_only_when_open(tmp_path):
    s = CooperativeSession(_ledger(tmp_path), clock=lambda: "ts")
    gate = CooperativeGate(s)
    assert gate.confirm(_action(Level.INPUT)) is False          # not open
    s.open(app="delta", pid=1)
    assert gate.confirm(_action(Level.INPUT)) is True           # within ceiling
    assert gate.confirm(_action(Level.AUTONOMOUS)) is False     # above ceiling
