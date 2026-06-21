from pathlib import Path

from daimon.setup.clients.registry import adapters_for_home, detected


def test_adapters_cover_known_clients():
    home = Path("/Users/test")
    names = {a.name for a in adapters_for_home(home)}
    assert {"Claude Code", "Claude Desktop", "Cursor", "Windsurf",
            "GitHub Copilot CLI", "Antigravity Desktop", "Antigravity IDE",
            "Antigravity CLI", "Codex", "Mistral Vibe"} <= names


def test_new_clients_have_correct_format():
    home = Path("/Users/test")
    by = {a.name: a for a in adapters_for_home(home)}
    assert by["Codex"].fmt == "toml-table"
    assert by["Codex"].config_path == home / ".codex" / "config.toml"
    assert by["Mistral Vibe"].fmt == "toml-array"
    assert by["GitHub Copilot CLI"].fmt == "json"
    assert by["Antigravity Desktop"].config_path == home / ".gemini" / "antigravity" / "mcp_config.json"


def test_paths_are_under_home():
    home = Path("/Users/test")
    by = {a.name: a for a in adapters_for_home(home)}
    assert str(by["Claude Code"].config_path).startswith(str(home))
    assert by["Claude Desktop"].config_path.name == "claude_desktop_config.json"


def test_detected_filters_by_existence(tmp_path):
    from daimon.setup.clients.base import ClientAdapter
    a = ClientAdapter(name="X", config_path=tmp_path / "exists.json")
    b = ClientAdapter(name="Y", config_path=tmp_path / "missing.json")
    a.config_path.write_text("{}")
    assert [x.name for x in detected([a, b])] == ["X"]
