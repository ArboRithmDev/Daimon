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
    monkeypatch.setattr("daimon.__main__._face_tray_available", lambda: False)  # NSMenu fallback
    ran = {}
    monkeypatch.setattr("daimon.tray.app.__main__.main", lambda: ran.setdefault("tray", True) or 0)
    m.main([])
    assert ran.get("tray") is True


def test_frozen_runs_face_tray_when_available(monkeypatch):
    # When pywebview + the built bundle are present, the glyph opens the webview face.
    monkeypatch.setattr(m.sys, "frozen", True, raising=False)
    monkeypatch.setattr("daimon.__main__._face_tray_available", lambda: True)
    ran = {}
    monkeypatch.setattr("daimon.face.tray.run", lambda: ran.setdefault("face", True) or 0)
    m.main([])
    assert ran.get("face") is True


def test_frozen_with_launch_services_arg_still_runs_tray(monkeypatch):
    # macOS may launch the .app with a stray `-psn_…` arg; it must NOT fall
    # through to the stdio server (which would wait on stdin and show nothing).
    monkeypatch.setattr(m.sys, "frozen", True, raising=False)
    monkeypatch.setattr("daimon.__main__._face_tray_available", lambda: False)
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


def test_overlay_subcommand_runs_overlay(monkeypatch):
    ran = {}
    monkeypatch.setattr("daimon.overlay.app.__main__.main",
                        lambda: ran.setdefault("overlay", True) or 0)
    assert m.main(["overlay"]) == 0
    assert ran.get("overlay") is True


def test_overlay_subcommand_runs_overlay_when_frozen(monkeypatch):
    # The frozen .app spawns the overlay via this subcommand; it must NOT fall
    # through to the tray (the bug that piled up duplicate menu-bar Daimons).
    monkeypatch.setattr(m.sys, "frozen", True, raising=False)
    ran = {}
    monkeypatch.setattr("daimon.overlay.app.__main__.main",
                        lambda: ran.setdefault("overlay", True) or 0)
    monkeypatch.setattr("daimon.tray.app.__main__.main",
                        lambda: ran.setdefault("tray", True) or 0)
    m.main(["overlay"])
    assert ran.get("overlay") is True
    assert ran.get("tray") is None, "overlay spawn must never start a tray"


def test_overlay_spawn_cmd_is_frozen_aware(monkeypatch):
    from daimon.overlay import launcher

    monkeypatch.setattr(launcher.sys, "frozen", True, raising=False)
    monkeypatch.setattr(launcher.sys, "executable", "/Applications/Daimon.app/Contents/MacOS/Daimon")
    # Frozen: address the dispatcher subcommand, NEVER `-m` (sys.executable is
    # the Daimon binary, not python — `-m` would launch a tray).
    assert launcher._overlay_cmd() == ["/Applications/Daimon.app/Contents/MacOS/Daimon", "overlay"]
    assert "-m" not in launcher._overlay_cmd()

    monkeypatch.setattr(launcher.sys, "frozen", False, raising=False)
    monkeypatch.setattr(launcher.sys, "executable", "/usr/bin/python3")
    assert launcher._overlay_cmd() == ["/usr/bin/python3", "-m", "daimon", "overlay"]
