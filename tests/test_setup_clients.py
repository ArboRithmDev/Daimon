import json
import pytest
from daimon.setup.clients.base import ClientAdapter, install, uninstall, status, read_config


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
