import json

from daimon.motor.audit import AppendOnlyLedger


def test_append_chains_hashes_and_verifies(tmp_path):
    ledger = AppendOnlyLedger(tmp_path / "ledger.jsonl")
    h1 = ledger.append({"event": "engage_l4", "ts": "2026-06-12T10:00:00Z"})
    h2 = ledger.append({"event": "disengage_l4", "ts": "2026-06-12T11:00:00Z"})
    assert h1 != h2
    lines = (tmp_path / "ledger.jsonl").read_text().splitlines()
    assert json.loads(lines[1])["prev_hash"] == h1
    assert ledger.verify()


def test_tampering_breaks_verification(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = AppendOnlyLedger(path)
    ledger.append({"event": "engage_l4", "ts": "t1"})
    ledger.append({"event": "act", "ts": "t2"})
    # Tamper with the first record's content.
    lines = path.read_text().splitlines()
    rec = json.loads(lines[0])
    rec["event"] = "FORGED"
    lines[0] = json.dumps(rec)
    path.write_text("\n".join(lines) + "\n")
    assert not ledger.verify()


def test_verify_empty_ledger_is_true(tmp_path):
    assert AppendOnlyLedger(tmp_path / "empty.jsonl").verify()
