# tests/test_main_dispatch.py
import daimon.__main__ as m


def test_subcommand_routes_to_cli(monkeypatch):
    calls = {}
    monkeypatch.setattr("daimon.setup.cli.run_command", lambda argv: calls.setdefault("argv", argv) or 0)
    code = m.main(["status"])
    assert calls["argv"] == ["status"] and code == 0


def test_no_arg_runs_server(monkeypatch):
    ran = {}
    monkeypatch.setattr("daimon.server.main", lambda: ran.setdefault("server", True))
    m.main([])
    assert ran.get("server") is True
