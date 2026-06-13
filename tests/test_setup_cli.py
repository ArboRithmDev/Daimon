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


def test_client_filter_targets_one(tmp_path, capsys):
    a = ClientAdapter("Alpha", tmp_path / "a.json")
    a.config_path.write_text("{}")
    b = ClientAdapter("Beta", tmp_path / "b.json")
    b.config_path.write_text("{}")
    run_command(["install", "--client", "Alpha"], adapters=[a, b])
    import json
    assert "daimon" in json.loads((tmp_path / "a.json").read_text()).get("mcpServers", {})
    assert "daimon" not in json.loads((tmp_path / "b.json").read_text()).get("mcpServers", {})


def test_no_detected_clients_warns(tmp_path, capsys):
    # adapters present but none detected (config paths don't exist)
    missing = ClientAdapter("Ghost", tmp_path / "nope.json")
    assert run_command(["status"], adapters=[missing]) == 0
    assert "no supported AI clients detected" in capsys.readouterr().out
