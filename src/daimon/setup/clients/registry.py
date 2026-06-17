"""The set of AI-client adapters Daimon knows how to register into."""

from __future__ import annotations

import sys
from pathlib import Path

from .base import ClientAdapter, PermSpec

# Antigravity's three surfaces share one permission shape: allow the daimon tools
# (mcp(daimon/*)), allow spawning the server binary (command(...)), and let it
# act system-wide (allowNonWorkspaceAccess — Daimon drives the whole desktop).
_AG_FLAGS = (("allowNonWorkspaceAccess", True),)


def _ag_perm(surface_dir: Path) -> PermSpec:
    return PermSpec(path=surface_dir / "settings.json",
                    allow=("mcp(daimon/*)",), allow_command=True, flags=_AG_FLAGS)


# Every Daimon MCP tool, by bare name — for clients that auto-approve by tool
# name (Mistral Vibe). Keep in sync with the tools registered in server.py /
# senses / motor (vue_*, touche_*, main_*, overlay_*).
DAIMON_TOOLS = (
    "vue_displays", "vue_snapshot", "touche_tree", "touche_probe",
    "main_click", "main_type", "main_press", "main_navigate", "main_key",
    "main_hover", "main_activate", "main_drag", "main_mouse_down",
    "main_mouse_up", "main_key_down", "main_key_up",
    "overlay_highlight", "overlay_spotlight", "overlay_cursor",
    "overlay_banner", "overlay_clear",
)


def _app_support(home: Path) -> Path:
    """Per-OS roaming app-data dir where GUI clients keep their config."""
    if sys.platform == "win32":
        return home / "AppData" / "Roaming"
    if sys.platform == "darwin":
        return home / "Library" / "Application Support"
    return home / ".config"


def adapters_for_home(home: Path) -> list[ClientAdapter]:
    """All known client adapters, resolved against *home* (testable seam)."""
    appsup = _app_support(home)
    gemini = home / ".gemini"
    return [
        # --- JSON mcpServers clients ---
        # Claude Code auto-approves a server's tools via permissions.allow in
        # ~/.claude/settings.json — "mcp__daimon__*" covers every daimon tool.
        ClientAdapter("Claude Code", home / ".claude.json",
                      detect_paths=(home / ".claude.json", home / ".claude"),
                      perm=PermSpec(path=home / ".claude" / "settings.json",
                                    allow=("mcp__daimon__*",))),
        ClientAdapter("Claude Desktop", appsup / "Claude" / "claude_desktop_config.json",
                      detect_paths=(appsup / "Claude", Path("/Applications/Claude.app"))),
        ClientAdapter("Cursor", home / ".cursor" / "mcp.json",
                      detect_paths=(home / ".cursor", Path("/Applications/Cursor.app"))),
        ClientAdapter("Windsurf", home / ".codeium" / "windsurf" / "mcp_config.json",
                      detect_paths=(home / ".codeium" / "windsurf", Path("/Applications/Windsurf.app"))),
        # Copilot CLI carries the grant in the entry itself: "tools": ["*"]
        # exposes every Daimon tool (matching the other servers it trusts).
        ClientAdapter("GitHub Copilot CLI", home / ".copilot" / "mcp-config.json",
                      detect_paths=(home / ".copilot",),
                      entry_extra={"tools": ["*"]}),
        # Antigravity (Gemini-based) — three surfaces, each its own mcp_config.json
        # + sibling settings.json carrying permissions.allow.
        ClientAdapter("Antigravity Desktop", gemini / "antigravity" / "mcp_config.json",
                      detect_paths=(gemini / "antigravity", Path("/Applications/Antigravity.app")),
                      perm=_ag_perm(gemini / "antigravity")),
        ClientAdapter("Antigravity IDE", gemini / "antigravity-ide" / "mcp_config.json",
                      detect_paths=(gemini / "antigravity-ide",),
                      perm=_ag_perm(gemini / "antigravity-ide")),
        ClientAdapter("Antigravity CLI", gemini / "antigravity-cli" / "mcp_config.json",
                      detect_paths=(gemini / "antigravity-cli",),
                      perm=_ag_perm(gemini / "antigravity-cli")),
        # --- TOML clients ---
        ClientAdapter("Codex", home / ".codex" / "config.toml", fmt="toml-table",
                      detect_paths=(home / ".codex", Path("/Applications/Codex.app"))),
        # Mistral Vibe auto-approves MCP tools by bare name in config.toml's
        # [mcp.auto_approve].tools array (same file as the server block).
        ClientAdapter("Mistral Vibe", home / ".vibe" / "config.toml", fmt="toml-array",
                      detect_paths=(home / ".vibe",),
                      perm=PermSpec(path=home / ".vibe" / "config.toml",
                                    toml_tools=DAIMON_TOOLS)),
    ]


def default_adapters() -> list[ClientAdapter]:
    """Adapters resolved against the real user home."""
    return adapters_for_home(Path.home())


def detected(adapters: list[ClientAdapter]) -> list[ClientAdapter]:
    """Subset of *adapters* whose client is actually installed."""
    return [a for a in adapters if a.detect()]
