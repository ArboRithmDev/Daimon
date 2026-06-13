# tests/test_main_dispatch.py
import daimon.__main__ as m


def test_subcommand_routes_to_cli(monkeypatch):
    calls = {}

    def _fake(argv):
        calls["argv"] = argv
        return 0

    monkeypatch.setattr("daimon.setup.cli.run_command", _fake)
    code = m.main(["status"])
    assert calls["argv"] == ["status"] and code == 0


def test_no_arg_runs_server_from_source(monkeypatch):
    # Not frozen (running from source): no-arg starts the MCP server.
    ran = {}
    monkeypatch.setattr("daimon.server.main", lambda: ran.setdefault("server", True))
    m.main([])
    assert ran.get("server") is True


def test_serve_runs_server(monkeypatch):
    ran = {}
    monkeypatch.setattr("daimon.server.main", lambda: ran.setdefault("server", True))
    assert m.main(["serve"]) == 0
    assert ran.get("server") is True


def test_no_arg_frozen_runs_tray(monkeypatch):
    monkeypatch.setattr(m.sys, "frozen", True, raising=False)
    ran = {}
    monkeypatch.setattr("daimon.tray.app.__main__.main", lambda: ran.setdefault("tray", True) or 0)
    m.main([])
    assert ran.get("tray") is True


def test_frozen_with_launch_services_arg_still_runs_tray(monkeypatch):
    # macOS may launch the .app with a stray `-psn_…` arg; it must NOT fall
    # through to the stdio server (which would wait on stdin and show nothing).
    monkeypatch.setattr(m.sys, "frozen", True, raising=False)
    ran = {}
    monkeypatch.setattr("daimon.tray.app.__main__.main", lambda: ran.setdefault("tray", True) or 0)
    m.main(["-psn_0_123456"])
    assert ran.get("tray") is True


def test_frozen_serve_still_runs_server(monkeypatch):
    monkeypatch.setattr(m.sys, "frozen", True, raising=False)
    ran = {}
    monkeypatch.setattr("daimon.server.main", lambda: ran.setdefault("server", True))
    m.main(["serve"])
    assert ran.get("server") is True


def test_gui_flag_runs_gui(monkeypatch):
    ran = {}
    monkeypatch.setattr("daimon.setup.gui.__main__.main", lambda: ran.setdefault("gui", True) or 0)
    m.main(["--gui"])
    assert ran.get("gui") is True
