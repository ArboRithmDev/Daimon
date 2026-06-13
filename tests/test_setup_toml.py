from daimon.setup.clients.base import ClientAdapter, install, status, uninstall

ENTRY = {"command": "/Applications/Daimon.app/Contents/MacOS/Daimon", "args": ["serve"], "env": {}}

EXISTING_CODEX = (
    'model = "gpt-5.5"\n\n'
    "[mcp_servers.other]\n"
    'command = "other-mcp"\n'
    "args = []\n"
)
EXISTING_VIBE = (
    'theme = "dark"\n\n'
    "[[mcp_servers]]\n"
    'name = "other"\n'
    'command = "other-mcp"\n'
)


def _codex(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text(EXISTING_CODEX, encoding="utf-8")
    return ClientAdapter("Codex", p, fmt="toml-table")


def _vibe(tmp_path):
    p = tmp_path / "config.toml"
    p.write_text(EXISTING_VIBE, encoding="utf-8")
    return ClientAdapter("Mistral Vibe", p, fmt="toml-array")


def test_codex_install_appends_table_block_and_preserves_rest(tmp_path):
    a = _codex(tmp_path)
    r = install(a, "daimon", ENTRY)
    assert r.action == "installed"
    text = a.config_path.read_text()
    assert "[mcp_servers.daimon]" in text
    assert 'args = ["serve"]' in text
    assert "# DAIMON:START" in text and "# DAIMON:END" in text
    assert "[mcp_servers.other]" in text and 'model = "gpt-5.5"' in text  # preserved


def test_vibe_install_appends_array_block(tmp_path):
    a = _vibe(tmp_path)
    install(a, "daimon", ENTRY)
    text = a.config_path.read_text()
    assert "[[mcp_servers]]" in text
    assert 'name = "daimon"' in text and 'transport = "stdio"' in text
    assert 'name = "other"' in text  # preserved


def test_toml_install_is_idempotent(tmp_path):
    a = _codex(tmp_path)
    install(a, "daimon", ENTRY)
    r = install(a, "daimon", ENTRY)
    assert r.action == "already"


def test_toml_uninstall_removes_only_daimon_block(tmp_path):
    a = _codex(tmp_path)
    install(a, "daimon", ENTRY)
    r = uninstall(a, "daimon")
    assert r.action == "removed"
    text = a.config_path.read_text()
    assert "# DAIMON:START" not in text and "[mcp_servers.daimon]" not in text
    assert "[mcp_servers.other]" in text  # other server untouched


def test_toml_status(tmp_path):
    a = _codex(tmp_path)
    assert status(a, "daimon").action == "absent"
    install(a, "daimon", ENTRY)
    assert status(a, "daimon").action == "present"


def test_toml_install_backs_up(tmp_path):
    a = _codex(tmp_path)
    install(a, "daimon", ENTRY)
    assert any(x.name.startswith("config.toml.bak") for x in tmp_path.iterdir())
