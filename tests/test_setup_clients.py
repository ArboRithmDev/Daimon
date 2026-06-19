import json
import pytest
from daimon.setup.clients.base import (
    ClientAdapter, install, uninstall, status, read_config,
    agy_tool_perms, install_agy_permissions, uninstall_agy_permissions,
    status_agy_permissions, _gemini_root,
)
from pathlib import Path


def _adapter(tmp_path, name="Test"):
    return ClientAdapter(name=name, config_path=tmp_path / "cfg.json")


ENTRY = {"command": "daimon", "args": [], "env": {}}


def test_install_creates_entry_and_backup(tmp_path):
    a = _adapter(tmp_path)
    r = install(a, "daimon", ENTRY)
    assert r.action == "installed"
    data = json.loads(a.config_path.read_text())
    assert data["mcpServers"]["daimon"] == ENTRY


def test_install_is_idempotent(tmp_path):
    a = _adapter(tmp_path)
    install(a, "daimon", ENTRY)
    r = install(a, "daimon", ENTRY)
    assert r.action == "already"


def test_install_preserves_other_servers_and_backs_up(tmp_path):
    a = _adapter(tmp_path)
    a.config_path.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}, "misc": 1}))
    install(a, "daimon", ENTRY)
    data = json.loads(a.config_path.read_text())
    assert data["mcpServers"]["other"] == {"command": "x"}
    assert data["misc"] == 1
    assert (tmp_path / "cfg.json.bak").exists() or any(p.name.startswith("cfg.json.bak") for p in tmp_path.iterdir())


def test_malformed_json_is_refused_not_overwritten(tmp_path):
    a = _adapter(tmp_path)
    a.config_path.write_text("{ not json")
    r = install(a, "daimon", ENTRY)
    assert r.action == "error"
    assert a.config_path.read_text() == "{ not json"  # untouched


def test_uninstall_removes_only_daimon(tmp_path):
    a = _adapter(tmp_path)
    a.config_path.write_text(json.dumps({"mcpServers": {"daimon": ENTRY, "other": {"command": "x"}}}))
    r = uninstall(a, "daimon")
    assert r.action == "removed"
    data = json.loads(a.config_path.read_text())
    assert "daimon" not in data["mcpServers"] and "other" in data["mcpServers"]


def test_status_reports_presence(tmp_path):
    a = _adapter(tmp_path)
    assert status(a, "daimon").action == "absent"
    install(a, "daimon", ENTRY)
    assert status(a, "daimon").action == "present"


def test_antigravity_enablement_handling(tmp_path):
    cli_dir = tmp_path / "antigravity-cli"
    cli_dir.mkdir(parents=True)
    
    a = ClientAdapter(name="Antigravity CLI", config_path=cli_dir / "mcp_config.json")
    enablement_path = tmp_path / "mcp-server-enablement.json"
    enablement_path.write_text(json.dumps({"other": {"enabled": False}}))
    
    r = install(a, "daimon", ENTRY)
    assert r.action == "installed"
    
    enablement_data = json.loads(enablement_path.read_text())
    assert enablement_data["daimon"] == {"enabled": True}
    assert enablement_data["other"] == {"enabled": False}
    
    r = uninstall(a, "daimon")
    assert r.action == "removed"
    
    enablement_data = json.loads(enablement_path.read_text())
    assert "daimon" not in enablement_data
    assert enablement_data["other"] == {"enabled": False}


# --- _gemini_root --------------------------------------------------------
def test_gemini_root_finds_dot_gemini_at_any_depth(tmp_path):
    g = tmp_path / ".gemini"
    assert _gemini_root(g / "config" / "mcp_config.json") == g   # two levels deep
    assert _gemini_root(g / "settings.json") == g                # one level deep


def test_gemini_root_falls_back_when_absent(tmp_path):
    p = tmp_path / "a" / "b" / "c.json"
    assert _gemini_root(p) == p.parent.parent


# --- Antigravity per-tool permissions ------------------------------------
TOOLS = ["vue_displays", "vue_snapshot", "main_click"]


def test_agy_tool_perms_enumerates_never_wildcards():
    perms = agy_tool_perms("daimon", TOOLS)
    assert perms == ["mcp(daimon/vue_displays)", "mcp(daimon/vue_snapshot)", "mcp(daimon/main_click)"]
    assert "mcp(daimon/*)" not in perms


def test_install_agy_permissions_creates_whitelist_and_backup(tmp_path):
    p = tmp_path / "settings.json"
    r = install_agy_permissions("AGY CLI perms", p, "daimon", TOOLS)
    assert r.action == "installed"
    allow = json.loads(p.read_text())["permissions"]["allow"]
    assert allow == agy_tool_perms("daimon", TOOLS)


def test_install_agy_permissions_idempotent(tmp_path):
    p = tmp_path / "settings.json"
    install_agy_permissions("L", p, "daimon", TOOLS)
    r = install_agy_permissions("L", p, "daimon", TOOLS)
    assert r.action == "already"


def test_install_agy_permissions_preserves_other_perms_and_keys(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({
        "security": {"auth": {"selectedType": "oauth"}},
        "permissions": {"allow": ["command(ls)", "mcp(other/foo)"]},
    }))
    install_agy_permissions("L", p, "daimon", TOOLS)
    data = json.loads(p.read_text())
    assert data["security"] == {"auth": {"selectedType": "oauth"}}
    assert "command(ls)" in data["permissions"]["allow"]
    assert "mcp(other/foo)" in data["permissions"]["allow"]
    assert "mcp(daimon/vue_displays)" in data["permissions"]["allow"]
    assert any(p2.name.startswith("settings.json.bak") for p2 in tmp_path.iterdir())


def test_install_agy_permissions_adds_safe_workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))
    ws = tmp_path / "proj"
    p = tmp_path / "settings.json"
    install_agy_permissions("L", p, "daimon", TOOLS, workspace=ws)
    tw = json.loads(p.read_text())["trustedWorkspaces"]
    assert str(ws) in tw


def test_install_agy_permissions_rejects_home_and_root_as_workspace(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    p = tmp_path / "settings.json"
    install_agy_permissions("L", p, "daimon", TOOLS, workspace=home)        # == $HOME
    install_agy_permissions("L", p, "daimon", TOOLS, workspace=Path("/"))   # == root
    data = json.loads(p.read_text())
    assert "trustedWorkspaces" not in data or data["trustedWorkspaces"] == []


def test_install_agy_permissions_refuses_malformed(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text("{ not json")
    r = install_agy_permissions("L", p, "daimon", TOOLS)
    assert r.action == "error"
    assert p.read_text() == "{ not json"


def test_uninstall_agy_permissions_removes_only_daimon(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({
        "permissions": {"allow": ["command(ls)", "mcp(daimon/vue_displays)", "mcp(other/x)"]},
        "trustedWorkspaces": ["/Users/x/proj"],
    }))
    r = uninstall_agy_permissions("L", p, "daimon")
    assert r.action == "removed"
    data = json.loads(p.read_text())
    assert data["permissions"]["allow"] == ["command(ls)", "mcp(other/x)"]
    assert data["trustedWorkspaces"] == ["/Users/x/proj"]   # left untouched


def test_uninstall_agy_permissions_absent_when_none(tmp_path):
    p = tmp_path / "settings.json"
    p.write_text(json.dumps({"permissions": {"allow": ["command(ls)"]}}))
    assert uninstall_agy_permissions("L", p, "daimon").action == "absent"


def test_status_agy_permissions(tmp_path):
    p = tmp_path / "settings.json"
    assert status_agy_permissions("L", p, "daimon", TOOLS).action == "absent"
    install_agy_permissions("L", p, "daimon", TOOLS)
    assert status_agy_permissions("L", p, "daimon", TOOLS).action == "present"

