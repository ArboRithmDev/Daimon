from daimon.setup.cli import run_command
from daimon.setup.clients.base import ClientAdapter


def _adapters(tmp_path):
    a = ClientAdapter("Test", tmp_path / "a.json")
    a.config_path.write_text("{}")   # detected
    return [a]


def test_status_runs(tmp_path, capsys):
    code = run_command(["status"], adapters=_adapters(tmp_path))
    assert code == 0
    assert "Test" in capsys.readouterr().out


def test_install_then_uninstall(tmp_path, capsys):
    ad = _adapters(tmp_path)
    assert run_command(["install", "--all"], adapters=ad) == 0
    import json
    assert "daimon" in json.loads((tmp_path / "a.json").read_text())["mcpServers"]
    assert run_command(["uninstall", "--all"], adapters=ad) == 0
    assert "daimon" not in json.loads((tmp_path / "a.json").read_text()).get("mcpServers", {})


def test_unknown_command_returns_nonzero(tmp_path):
    assert run_command(["frobnicate"], adapters=_adapters(tmp_path)) != 0
