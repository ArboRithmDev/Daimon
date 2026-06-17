"""Granting/revoking maximum client permission (the zero-friction red-line)."""

import json

from daimon.setup.clients.base import (
    ClientAdapter, PermSpec, grant_permissions, revoke_permissions,
)

_ENTRY = {"command": r"C:\Apps\Daimon\Daimon.exe", "args": ["serve"], "env": {}}


def _claude_adapter(tmp_path):
    return ClientAdapter("Claude Code", tmp_path / ".claude.json",
                         perm=PermSpec(path=tmp_path / "settings.json",
                                       allow=("mcp__daimon__*",)))


def _ag_adapter(tmp_path):
    return ClientAdapter("Antigravity CLI", tmp_path / "mcp_config.json",
                         perm=PermSpec(path=tmp_path / "settings.json",
                                       allow=("mcp(daimon/*)",), allow_command=True,
                                       flags=(("allowNonWorkspaceAccess", True),)))


def test_grant_creates_allow_list_when_settings_absent(tmp_path):
    a = _claude_adapter(tmp_path)
    r = grant_permissions(a, _ENTRY)
    assert r.action == "granted"
    cfg = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert cfg["permissions"]["allow"] == ["mcp__daimon__*"]


def test_grant_is_idempotent(tmp_path):
    a = _claude_adapter(tmp_path)
    grant_permissions(a, _ENTRY)
    r = grant_permissions(a, _ENTRY)
    assert r.action == "already"


def test_grant_preserves_existing_settings_and_allow_entries(tmp_path):
    settings = tmp_path / "settings.json"
    settings.write_text(json.dumps({
        "colorScheme": "dark",
        "permissions": {"allow": ["command(pytest)"]},
    }), encoding="utf-8")
    a = _ag_adapter(tmp_path)
    grant_permissions(a, _ENTRY)
    cfg = json.loads(settings.read_text(encoding="utf-8"))
    assert cfg["colorScheme"] == "dark"                       # untouched
    assert "command(pytest)" in cfg["permissions"]["allow"]   # preserved
    assert "mcp(daimon/*)" in cfg["permissions"]["allow"]
    assert r"command(C:\Apps\Daimon\Daimon.exe)" in cfg["permissions"]["allow"]
    assert cfg["allowNonWorkspaceAccess"] is True             # flag set


def test_revoke_removes_only_our_entries(tmp_path):
    a = _ag_adapter(tmp_path)
    # seed with a foreign entry + grant ours
    (tmp_path / "settings.json").write_text(
        json.dumps({"permissions": {"allow": ["command(pytest)"]}}), encoding="utf-8")
    grant_permissions(a, _ENTRY)
    r = revoke_permissions(a, _ENTRY)
    assert r.action == "removed"
    allow = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))["permissions"]["allow"]
    assert allow == ["command(pytest)"]                       # foreign kept, ours gone
    # flag is intentionally left in place (may govern other tools)


def test_grant_skipped_when_no_perm_mechanism(tmp_path):
    a = ClientAdapter("Cursor", tmp_path / "mcp.json")  # perm=None
    assert grant_permissions(a, _ENTRY).action == "skipped"


def test_grant_errors_on_malformed_settings(tmp_path):
    (tmp_path / "settings.json").write_text("{ not json", encoding="utf-8")
    a = _claude_adapter(tmp_path)
    assert grant_permissions(a, _ENTRY).action == "error"
