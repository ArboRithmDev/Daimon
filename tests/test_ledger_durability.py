from daimon.motor.audit import AppendOnlyLedger
from daimon.motor.consent import ConsentManager
from daimon.motor.types import Level


def test_append_still_verifies_under_lock(tmp_path):
    led = AppendOnlyLedger(tmp_path / "l.jsonl")
    led.append({"event": "a", "ts": "1"})
    led.append({"event": "b", "ts": "2"})
    assert led.verify()


def test_state_engaged_without_ledger_event_is_rejected(tmp_path):
    # Forged state file says engaged, but the ledger has no engage_l4 → fail-safe.
    import json
    state = tmp_path / "state.json"; state.write_text(json.dumps({"engaged": True}))
    led = AppendOnlyLedger(tmp_path / "consent.jsonl")  # empty ledger
    m = ConsentManager(config_ceiling=Level.READ, engagement_phrase="G",
                       disengagement_phrase="S", ledger=led, state_path=state)
    assert m.current_ceiling() == Level.READ  # not AUTONOMOUS — forgery rejected


def test_genuine_engagement_is_honored(tmp_path):
    state = tmp_path / "state.json"
    led = AppendOnlyLedger(tmp_path / "consent.jsonl")
    m = ConsentManager(config_ceiling=Level.READ, engagement_phrase="G",
                       disengagement_phrase="S", ledger=led, state_path=state)
    m.engage("G", ts="1")
    assert m.current_ceiling() == Level.AUTONOMOUS
