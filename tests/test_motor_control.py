from daimon.motor.control import run_command
from daimon.motor.types import Level


def test_engage_then_status_then_disengage(tmp_path, capsys):
    cfg_state = tmp_path / "motor.state.json"
    ledger = tmp_path / "consent.jsonl"
    kw = dict(
        config_ceiling=Level.READ,
        engagement_phrase="GO", disengagement_phrase="STOP",
        ledger_path=ledger, state_path=cfg_state,
    )
    assert run_command("engage", typed="GO", **kw) == 0
    assert run_command("status", typed=None, **kw) == 0
    assert "AUTONOMOUS" in capsys.readouterr().out
    assert run_command("engage", typed="wrong", **kw) == 1
    assert run_command("disengage", typed="STOP", **kw) == 0
    assert "READ" in capsys.readouterr().out or run_command("status", typed=None, **kw) == 0
