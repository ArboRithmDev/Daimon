import sys
from pathlib import Path

import pytest

from daimon.setup.clients.registry import adapters_for_home, detected


def test_adapters_cover_known_clients():
    home = Path("/Users/test")
    names = {a.name for a in adapters_for_home(home)}
    assert {"Claude Code", "Claude Desktop", "Cursor", "Windsurf",
            "GitHub Copilot CLI", "Antigravity Desktop", "Antigravity IDE",
            "Antigravity CLI", "Codex", "Mistral Vibe"} <= names


@pytest.mark.skipif(sys.platform == "win32",
                    reason="POSIX-path assertions; client paths + registry_win land in W4")
def test_new_clients_have_correct_format():
    home = Path("/Users/test")
    by = {a.name: a for a in adapters_for_home(home)}
    assert by["Codex"].fmt == "toml-table"
    assert str(by["Codex"].config_path).endswith(".codex/config.toml")
    assert by["Mistral Vibe"].fmt == "toml-array"
    assert by["GitHub Copilot CLI"].fmt == "json"
    assert "antigravity/mcp_config.json" in str(by["Antigravity Desktop"].config_path)


@pytest.mark.skipif(sys.platform == "win32",
                    reason="POSIX-path assertions; client paths + registry_win land in W4")
def test_paths_are_under_home():
    home = Path("/Users/test")
    by = {a.name: a for a in adapters_for_home(home)}
    assert str(by["Claude Code"].config_path).startswith("/Users/test")
    assert "claude_desktop_config.json" in str(by["Claude Desktop"].config_path)


def test_detected_filters_by_existence(tmp_path):
    from daimon.setup.clients.base import ClientAdapter
    a = ClientAdapter(name="X", config_path=tmp_path / "exists.json")
    b = ClientAdapter(name="Y", config_path=tmp_path / "missing.json")
    a.config_path.write_text("{}")
    assert [x.name for x in detected([a, b])] == ["X"]
