from daimon.motor.audit import AppendOnlyLedger
from daimon.motor.consent import ConsentManager
from daimon.motor.types import Level


def _manager(tmp_path, config_ceiling=Level.READ):
    return ConsentManager(
        config_ceiling=config_ceiling,
        engagement_phrase="I ENGAGE L4 AUTONOMY",
        disengagement_phrase="I DISENGAGE L4 AUTONOMY",
        ledger=AppendOnlyLedger(tmp_path / "consent.jsonl"),
        state_path=tmp_path / "motor.state.json",
    )


def test_default_ceiling_is_config(tmp_path):
    m = _manager(tmp_path, Level.VALIDATION)
    assert m.current_ceiling() == Level.VALIDATION


def test_engage_with_correct_phrase_raises_to_l4(tmp_path):
    m = _manager(tmp_path)
    assert m.engage("I ENGAGE L4 AUTONOMY", ts="t1") is True
    assert m.current_ceiling() == Level.AUTONOMOUS
    assert m._ledger.verify()


def test_engage_with_wrong_phrase_refused(tmp_path):
    m = _manager(tmp_path)
    assert m.engage("please let me", ts="t1") is False
    assert m.current_ceiling() == Level.READ


def test_disengage_requires_symmetric_phrase(tmp_path):
    m = _manager(tmp_path)
    m.engage("I ENGAGE L4 AUTONOMY", ts="t1")
    assert m.disengage("nope", ts="t2") is False
    assert m.current_ceiling() == Level.AUTONOMOUS
    assert m.disengage("I DISENGAGE L4 AUTONOMY", ts="t3") is True
    assert m.current_ceiling() == Level.READ


def test_engagement_survives_new_manager_instance(tmp_path):
    _manager(tmp_path).engage("I ENGAGE L4 AUTONOMY", ts="t1")
    # A fresh manager (e.g. the MCP server process) sees the state file.
    assert _manager(tmp_path).current_ceiling() == Level.AUTONOMOUS


def test_engage_confirmed_raises_ceiling_and_is_ledgered(tmp_path):
    m = _manager(tmp_path, Level.VALIDATION)
    assert m.current_ceiling() == Level.VALIDATION
    assert m.engage_confirmed(ts="2026-06-20T10:00:00Z") is True
    assert m.current_ceiling() == Level.AUTONOMOUS
    last = m._ledger._records()[-1]
    assert last["event"] == "engage_l4" and last["method"] == "confirmed"
    # disengage still works and drops back to config
    assert m.disengage("I DISENGAGE L4 AUTONOMY", ts="2026-06-20T10:05:00Z") is True
    assert m.current_ceiling() == Level.VALIDATION


def test_engaged_state_without_ledger_event_does_not_grant_l4(tmp_path):
    # Anti-forge: a state file flipped to engaged but no engage_l4 ledger event = still config.
    import json
    ledger = AppendOnlyLedger(tmp_path / "consent.jsonl")
    state = tmp_path / "motor.state.json"
    state.write_text(json.dumps({"engaged": True, "ts": "x"}), encoding="utf-8")
    m = ConsentManager(Level.VALIDATION, "E", "D", ledger, state)
    assert m.current_ceiling() == Level.VALIDATION
