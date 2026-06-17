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


# --- Copilot CLI: grant carried in the entry (tools: ["*"]) -----------------

def test_copilot_entry_carries_tools_wildcard(tmp_path):
    from daimon.setup.clients.base import install
    a = ClientAdapter("GitHub Copilot CLI", tmp_path / "mcp-config.json",
                      entry_extra={"tools": ["*"]})
    install(a, "daimon", _ENTRY)
    cfg = json.loads((tmp_path / "mcp-config.json").read_text(encoding="utf-8"))
    assert cfg["mcpServers"]["daimon"]["tools"] == ["*"]
    assert cfg["mcpServers"]["daimon"]["command"] == _ENTRY["command"]


# --- Mistral Vibe: TOML [mcp.auto_approve].tools ----------------------------

_VIBE_TOOLS = ("vue_snapshot", "main_click", "overlay_clear")


def _vibe_adapter(tmp_path):
    return ClientAdapter("Mistral Vibe", tmp_path / "config.toml", fmt="toml-array",
                         perm=PermSpec(path=tmp_path / "config.toml", toml_tools=_VIBE_TOOLS))


def test_vibe_grant_appends_section_when_absent(tmp_path):
    (tmp_path / "config.toml").write_text('[mcp]\nfoo = 1\n', encoding="utf-8")
    a = _vibe_adapter(tmp_path)
    assert grant_permissions(a, _ENTRY).action == "granted"
    text = (tmp_path / "config.toml").read_text(encoding="utf-8")
    assert "[mcp.auto_approve]" in text
    for t in _VIBE_TOOLS:
        assert f'"{t}"' in text


def test_vibe_grant_preserves_foreign_tools_and_is_idempotent(tmp_path):
    (tmp_path / "config.toml").write_text(
        '[mcp.auto_approve]\ntools = [\n    "executeQuery",\n    "mem_help",\n]\n',
        encoding="utf-8")
    a = _vibe_adapter(tmp_path)
    grant_permissions(a, _ENTRY)
    text = (tmp_path / "config.toml").read_text(encoding="utf-8")
    assert '"executeQuery"' in text and '"mem_help"' in text   # foreign kept
    for t in _VIBE_TOOLS:
        assert f'"{t}"' in text
    # parseable TOML + idempotent
    import tomllib
    parsed = tomllib.loads(text)
    assert set(_VIBE_TOOLS) <= set(parsed["mcp"]["auto_approve"]["tools"])
    assert grant_permissions(a, _ENTRY).action == "already"


def test_vibe_revoke_removes_only_daimon_tools(tmp_path):
    (tmp_path / "config.toml").write_text(
        '[mcp.auto_approve]\ntools = [\n    "executeQuery",\n]\n', encoding="utf-8")
    a = _vibe_adapter(tmp_path)
    grant_permissions(a, _ENTRY)
    assert revoke_permissions(a, _ENTRY).action == "removed"
    import tomllib
    tools = tomllib.loads((tmp_path / "config.toml").read_text(encoding="utf-8"))["mcp"]["auto_approve"]["tools"]
    assert tools == ["executeQuery"]   # foreign kept, daimon tools gone
