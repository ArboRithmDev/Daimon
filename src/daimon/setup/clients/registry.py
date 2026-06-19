"""The set of AI-client adapters Daimon knows how to register into."""

from __future__ import annotations

from pathlib import Path

from .base import ClientAdapter


def adapters_for_home(home: Path) -> list[ClientAdapter]:
    """All known client adapters, resolved against *home* (testable seam)."""
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
        # Antigravity (Gemini-based) — three surfaces, each its own mcp_config.json, plus a global one.
        # The global config + settings.json are inherited by every AGY surface (R1 of the
        # AGY deploy doctrine), so they're the primary server-declaration targets.
        ClientAdapter("Antigravity Global", gemini / "config" / "mcp_config.json",
                      detect_paths=(gemini / "config",)),
        ClientAdapter("Antigravity Settings", gemini / "settings.json",
                      detect_paths=(gemini,)),
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


def agy_permission_surfaces_for_home(home: Path) -> list[tuple[str, Path, Path]]:
    """(label, settings_path, detect_dir) per AGY surface needing an explicit
    per-tool permission whitelist (R2 of the AGY deploy doctrine).

    Server declaration is global (inherited), but AGY's Security Manager enforces
    tool access from each surface's *own* settings.json, so the whitelist is written
    per surface — only for surfaces actually present on the machine.
    """
    g = home / ".gemini"
    return [
        ("Antigravity Desktop perms", g / "antigravity" / "settings.json", g / "antigravity"),
        ("Antigravity IDE perms", g / "antigravity-ide" / "settings.json", g / "antigravity-ide"),
        ("Antigravity CLI perms", g / "antigravity-cli" / "settings.json", g / "antigravity-cli"),
    ]


def default_adapters() -> list[ClientAdapter]:
    """Adapters resolved against the real user home."""
    return adapters_for_home(Path.home())


def detected(adapters: list[ClientAdapter]) -> list[ClientAdapter]:
    """Subset of *adapters* whose client is actually installed."""
    return [a for a in adapters if a.detect()]
