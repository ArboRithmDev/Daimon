"""The set of AI-client adapters Daimon knows how to register into."""

from __future__ import annotations

from pathlib import Path

from .base import ClientAdapter


def adapters_for_home(home: Path) -> list[ClientAdapter]:
    appsup = home / "Library" / "Application Support"
    gemini = home / ".gemini"
    return [
        # --- JSON mcpServers clients ---
        ClientAdapter("Claude Code", home / ".claude.json",
                      detect_paths=(home / ".claude.json", home / ".claude")),
        ClientAdapter("Claude Desktop", appsup / "Claude" / "claude_desktop_config.json",
                      detect_paths=(appsup / "Claude", Path("/Applications/Claude.app"))),
        ClientAdapter("Cursor", home / ".cursor" / "mcp.json",
                      detect_paths=(home / ".cursor", Path("/Applications/Cursor.app"))),
        ClientAdapter("Windsurf", home / ".codeium" / "windsurf" / "mcp_config.json",
                      detect_paths=(home / ".codeium" / "windsurf", Path("/Applications/Windsurf.app"))),
        ClientAdapter("GitHub Copilot CLI", home / ".copilot" / "mcp-config.json",
                      detect_paths=(home / ".copilot",)),
        # Antigravity (Gemini-based) — three surfaces, each its own mcp_config.json.
        ClientAdapter("Antigravity Desktop", gemini / "antigravity" / "mcp_config.json",
                      detect_paths=(gemini / "antigravity", Path("/Applications/Antigravity.app"))),
        ClientAdapter("Antigravity IDE", gemini / "antigravity-ide" / "mcp_config.json",
                      detect_paths=(gemini / "antigravity-ide",)),
        ClientAdapter("Antigravity CLI", gemini / "antigravity-cli" / "mcp_config.json",
                      detect_paths=(gemini / "antigravity-cli",)),
        # --- TOML clients ---
        ClientAdapter("Codex", home / ".codex" / "config.toml", fmt="toml-table",
                      detect_paths=(home / ".codex", Path("/Applications/Codex.app"))),
        ClientAdapter("Mistral Vibe", home / ".vibe" / "config.toml", fmt="toml-array",
                      detect_paths=(home / ".vibe",)),
    ]


def default_adapters() -> list[ClientAdapter]:
    return adapters_for_home(Path.home())


def detected(adapters: list[ClientAdapter]) -> list[ClientAdapter]:
    return [a for a in adapters if a.detect()]
