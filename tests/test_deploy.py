import json

from daimon.setup import deploy
from daimon.setup.clients.base import ClientAdapter


def _adapters(tmp_path):
    a = ClientAdapter("Alpha", tmp_path / "a.json")
    b = ClientAdapter("Beta", tmp_path / "b.json")
    a.config_path.write_text("{}")  # detected
    b.config_path.write_text("{}")
    return [a, b]


def _no_agy(monkeypatch):
    """Keep install_all/uninstall off the real ~/.gemini in client-level tests."""
    monkeypatch.setattr(deploy, "agy_permission_surfaces_for_home", lambda home: [])


def test_install_all_registers_each_detected(tmp_path, monkeypatch):
    adapters = _adapters(tmp_path)
    monkeypatch.setattr(deploy, "default_adapters", lambda: adapters)
    monkeypatch.setattr(deploy, "detected", lambda a: a)
    _no_agy(monkeypatch)
    results = deploy.install_all()
    assert {r.action for r in results} == {"installed"}
    assert "daimon" in json.loads((tmp_path / "a.json").read_text())["mcpServers"]
    assert "daimon" in json.loads((tmp_path / "b.json").read_text())["mcpServers"]


def test_client_summary_counts(tmp_path, monkeypatch):
    adapters = _adapters(tmp_path)
    monkeypatch.setattr(deploy, "default_adapters", lambda: adapters)
    monkeypatch.setattr(deploy, "detected", lambda a: a)
    _no_agy(monkeypatch)
    assert deploy.client_summary() == (0, 2)
    deploy.install_all()
    assert deploy.client_summary() == (2, 2)


# --- AGY per-surface permission deployment -------------------------------
def _agy_surfaces(tmp_path):
    """Two 'present' surfaces + one absent, the registry's (label, settings, det) shape."""
    desk = tmp_path / "antigravity"
    ide = tmp_path / "antigravity-ide"
    desk.mkdir()
    ide.mkdir()
    cli = tmp_path / "antigravity-cli"  # not created → absent
    return [
        ("AGY Desktop perms", desk / "settings.json", desk),
        ("AGY IDE perms", ide / "settings.json", ide),
        ("AGY CLI perms", cli / "settings.json", cli),
    ]


def test_install_agy_permissions_all_only_present_surfaces(tmp_path):
    surfaces = _agy_surfaces(tmp_path)
    results = deploy.install_agy_permissions_all(
        surfaces=surfaces, tools=["vue_displays", "main_click"])
    assert [r.action for r in results] == ["installed", "installed"]  # CLI absent → skipped
    desk_allow = json.loads((tmp_path / "antigravity" / "settings.json").read_text())["permissions"]["allow"]
    assert "mcp(daimon/vue_displays)" in desk_allow and "mcp(daimon/main_click)" in desk_allow


def test_install_agy_permissions_all_no_surfaces_skips_server_build(tmp_path, monkeypatch):
    # tools=None would normally build the server; with no present surface it must not.
    def _boom():
        raise AssertionError("daimon_tool_names should not be called when no surface is present")
    monkeypatch.setattr(deploy, "daimon_tool_names", _boom)
    assert deploy.install_agy_permissions_all(surfaces=[]) == []


def test_uninstall_agy_permissions_all_reversible(tmp_path):
    surfaces = _agy_surfaces(tmp_path)
    deploy.install_agy_permissions_all(surfaces=surfaces, tools=["vue_displays"])
    results = deploy.uninstall_agy_permissions_all(surfaces=surfaces)
    assert [r.action for r in results] == ["removed", "removed"]
    desk = json.loads((tmp_path / "antigravity" / "settings.json").read_text())
    assert desk["permissions"]["allow"] == []


def test_daimon_tool_names_matches_live_server():
    names = deploy.daimon_tool_names()
    # The 21 tools the AGY whitelist must cover, sourced from the live server.
    assert {"vue_displays", "vue_snapshot", "touche_tree", "touche_probe",
            "main_click", "main_drag", "overlay_highlight", "overlay_clear"} <= set(names)
    assert all(isinstance(n, str) for n in names)
