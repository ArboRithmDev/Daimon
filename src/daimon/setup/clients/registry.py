"""The set of AI-client adapters Daimon knows how to register into."""

from __future__ import annotations

from pathlib import Path

from .base import ClientAdapter


def adapters_for_home(home: Path) -> list[ClientAdapter]:
    appsup = home / "Library" / "Application Support"
    return [
        ClientAdapter("Claude Code", home / ".claude.json",
                      detect_paths=(home / ".claude.json", home / ".claude")),
        ClientAdapter("Claude Desktop", appsup / "Claude" / "claude_desktop_config.json",
                      detect_paths=(appsup / "Claude", Path("/Applications/Claude.app"))),
        ClientAdapter("Cursor", home / ".cursor" / "mcp.json",
                      detect_paths=(home / ".cursor", Path("/Applications/Cursor.app"))),
        ClientAdapter("Windsurf", home / ".codeium" / "windsurf" / "mcp_config.json",
                      detect_paths=(home / ".codeium" / "windsurf", Path("/Applications/Windsurf.app"))),
    ]


def default_adapters() -> list[ClientAdapter]:
    return adapters_for_home(Path.home())


def detected(adapters: list[ClientAdapter]) -> list[ClientAdapter]:
    return [a for a in adapters if a.detect()]
