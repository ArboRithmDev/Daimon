"""Client adapter + idempotent, reversible, safe MCP-config registration.

Three config formats are supported (set per adapter via ``fmt``):
  * ``"json"``       — JSON file with an ``mcpServers`` object (Claude Code/Desktop,
                       Cursor, Windsurf, Copilot CLI, Antigravity).
  * ``"toml-table"`` — TOML with ``[mcp_servers.<name>]`` tables (Codex).
  * ``"toml-array"`` — TOML with ``[[mcp_servers]]`` array-of-tables (Mistral Vibe).

JSON is merged in place. TOML formats use a marker-delimited block
(``# DAIMON:START`` … ``# DAIMON:END``) appended/replaced in the file, so the
rest of the user's TOML (other servers, settings) is never reparsed or touched —
safe, idempotent, reversible. Every write is backed up + atomic.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

_MARK_START = "# DAIMON:START"
_MARK_END = "# DAIMON:END"
_BLOCK_RE = re.compile(re.escape(_MARK_START) + r".*?" + re.escape(_MARK_END) + r"\n?", re.DOTALL)


@dataclass(frozen=True)
class ClientAdapter:
    """One AI client: where its config lives and which format (json/toml) it uses."""
    name: str
    config_path: Path
    key: str = "mcpServers"
    detect_paths: tuple[Path, ...] = ()
    fmt: str = "json"   # json | toml-table | toml-array

    def detect(self) -> bool:
        """True if any detect path exists, i.e. this client is installed."""
        paths = self.detect_paths or (self.config_path,)
        return any(Path(p).exists() for p in paths)


@dataclass(frozen=True)
class Result:
    """Outcome of an install/uninstall/status op against one client."""
    client: str
    action: str   # installed|already|removed|absent|present|not_found|error
    detail: str = ""


def read_config(path: Path) -> dict:
    """Parse a client config; {} if missing; raise ValueError if malformed."""
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    data = json.loads(text)   # JSONDecodeError (ValueError) on malformed
    if not isinstance(data, dict):
        raise ValueError("client config is not a JSON object")
    return data


def _atomic_write(path: Path, data: dict, *, backup: bool, ts: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if backup and path.exists():
        path.with_name(f"{path.name}.bak.{ts}").write_text(
            path.read_text(encoding="utf-8"), encoding="utf-8")
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


# --- TOML (marker-block) format ------------------------------------------
def _toml_str(s) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def _toml_block(fmt: str, name: str, entry: dict) -> str:
    cmd = _toml_str(entry["command"])
    args = "[" + ", ".join(_toml_str(a) for a in entry.get("args", [])) + "]"
    if fmt == "toml-array":
        body = (f"[[mcp_servers]]\nname = {_toml_str(name)}\n"
                f'transport = "stdio"\ncommand = {cmd}\nargs = {args}')
    else:  # toml-table
        body = f"[mcp_servers.{name}]\ncommand = {cmd}\nargs = {args}"
    return f"{_MARK_START}\n{body}\n{_MARK_END}"


def _write_text(path: Path, text: str, *, ts: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.with_name(f"{path.name}.bak.{ts}").write_text(
            path.read_text(encoding="utf-8"), encoding="utf-8")
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def _install_toml(adapter: ClientAdapter, name: str, entry: dict, ts: str) -> Result:
    path = adapter.config_path
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    block = _toml_block(adapter.fmt, name, entry)
    m = _BLOCK_RE.search(existing)
    if m and m.group(0).strip() == block.strip():
        return Result(adapter.name, "already", "daimon already registered")
    stripped = _BLOCK_RE.sub("", existing).rstrip()
    new = (stripped + "\n\n" if stripped else "") + block + "\n"
    _write_text(path, new, ts=ts)
    return Result(adapter.name, "installed", str(path))


def _uninstall_toml(adapter: ClientAdapter, ts: str) -> Result:
    path = adapter.config_path
    if not path.exists():
        return Result(adapter.name, "absent", "daimon not registered")
    existing = path.read_text(encoding="utf-8")
    if _MARK_START not in existing:
        return Result(adapter.name, "absent", "daimon not registered")
    new = _BLOCK_RE.sub("", existing).rstrip() + "\n"
    _write_text(path, new, ts=ts)
    return Result(adapter.name, "removed", str(path))


def _status_toml(adapter: ClientAdapter) -> Result:
    path = adapter.config_path
    present = path.exists() and _MARK_START in path.read_text(encoding="utf-8")
    return Result(adapter.name, "present" if present else "absent", str(path))


def _gemini_root(path: Path) -> Path:
    """The ``.gemini`` dir nearest above *path* — where the global enablement lives.

    Robust to how deep the adapter's config sits (``.gemini/config/mcp_config.json``
    vs ``.gemini/settings.json``); falls back to the legacy two-levels-up guess.
    """
    for parent in path.parents:
        if parent.name == ".gemini":
            return parent
    return path.parent.parent


def _enable_in_gemini(gemini_dir: Path, name: str) -> None:
    enablement_path = gemini_dir / "mcp-server-enablement.json"
    try:
        if enablement_path.exists():
            text = enablement_path.read_text(encoding="utf-8").strip()
            data = json.loads(text) if text else {}
        else:
            data = {}
        if not isinstance(data, dict):
            data = {}
        if data.get(name, {}).get("enabled") is not True:
            data.setdefault(name, {})["enabled"] = True
            tmp = enablement_path.with_name(f"{enablement_path.name}.tmp")
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            os.replace(tmp, enablement_path)
    except Exception:
        pass


def _disable_in_gemini(gemini_dir: Path, name: str) -> None:
    enablement_path = gemini_dir / "mcp-server-enablement.json"
    try:
        if enablement_path.exists():
            text = enablement_path.read_text(encoding="utf-8").strip()
            data = json.loads(text) if text else {}
            if isinstance(data, dict) and name in data:
                data.pop(name)
                tmp = enablement_path.with_name(f"{enablement_path.name}.tmp")
                tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                os.replace(tmp, enablement_path)
    except Exception:
        pass


def install(adapter: ClientAdapter, name: str, entry: dict, *, ts: str = "0") -> Result:
    """Register *entry* under *name*; idempotent, backed-up, atomic."""
    if adapter.fmt in ("toml-table", "toml-array"):
        return _install_toml(adapter, name, entry, ts)
    try:
        cfg = read_config(adapter.config_path)
    except ValueError as e:
        return Result(adapter.name, "error", f"malformed config: {e}")
    servers = cfg.setdefault(adapter.key, {})
    if not isinstance(servers, dict):
        return Result(adapter.name, "error", f"'{adapter.key}' is not an object")
    if servers.get(name) == entry:
        if adapter.name.startswith("Antigravity"):
            _enable_in_gemini(_gemini_root(adapter.config_path), name)
        return Result(adapter.name, "already", "daimon already registered")
    servers[name] = entry
    _atomic_write(adapter.config_path, cfg, backup=True, ts=ts)
    if adapter.name.startswith("Antigravity"):
        _enable_in_gemini(_gemini_root(adapter.config_path), name)
    return Result(adapter.name, "installed", str(adapter.config_path))


def uninstall(adapter: ClientAdapter, name: str, *, ts: str = "0") -> Result:
    """Remove *name* from the client config; backed-up and atomic (reversible)."""
    if adapter.fmt in ("toml-table", "toml-array"):
        return _uninstall_toml(adapter, ts)
    try:
        cfg = read_config(adapter.config_path)
    except ValueError as e:
        return Result(adapter.name, "error", f"malformed config: {e}")
    servers = cfg.get(adapter.key, {})
    if not isinstance(servers, dict) or name not in servers:
        return Result(adapter.name, "absent", "daimon not registered")
    servers.pop(name)
    _atomic_write(adapter.config_path, cfg, backup=True, ts=ts)
    if adapter.name.startswith("Antigravity"):
        _disable_in_gemini(_gemini_root(adapter.config_path), name)
    return Result(adapter.name, "removed", str(adapter.config_path))


def status(adapter: ClientAdapter, name: str) -> Result:
    """Report whether *name* is currently registered in the client config."""
    if adapter.fmt in ("toml-table", "toml-array"):
        return _status_toml(adapter)
    try:
        cfg = read_config(adapter.config_path)
    except ValueError:
        return Result(adapter.name, "error", "malformed config")
    servers = cfg.get(adapter.key, {})
    present = isinstance(servers, dict) and name in servers
    return Result(adapter.name, "present" if present else "absent", str(adapter.config_path))


# --- Antigravity per-surface tool permissions ----------------------------
# Declaring + enabling a server is necessary but NOT sufficient for AGY: its
# Security Manager rejects each tool call unless `mcp(server/<tool>)` is in the
# surface's settings.json `permissions.allow`. Wildcards (`mcp(server/*)`) are
# rejected at the resource-listing step, so every tool must be listed explicitly.
def agy_tool_perms(server: str, tools) -> list[str]:
    """The explicit per-tool allow entries for an AGY surface — never a wildcard."""
    return [f"mcp({server}/{t})" for t in tools]


def _is_safe_workspace(ws, home) -> bool:
    """True if *ws* is a real project dir worth trusting (not the filesystem root or $HOME)."""
    ws = Path(ws)
    return ws.is_absolute() and ws != Path(ws.anchor) and ws != Path(home)


def install_agy_permissions(label: str, path: Path, server: str, tools, *,
                            workspace=None, ts: str = "0") -> Result:
    """Whitelist each ``mcp(server/<tool>)`` in a surface's settings.json
    ``permissions.allow`` (+ optionally trust *workspace*).

    Idempotent, backed-up, atomic, reversible — never touches other servers'
    permissions, other settings keys, or pre-existing trusted workspaces.
    """
    try:
        cfg = read_config(path)
    except ValueError as e:
        return Result(label, "error", f"malformed config: {e}")
    perms = cfg.setdefault("permissions", {})
    if not isinstance(perms, dict):
        return Result(label, "error", "'permissions' is not an object")
    allow = perms.setdefault("allow", [])
    if not isinstance(allow, list):
        return Result(label, "error", "'permissions.allow' is not a list")

    wanted = agy_tool_perms(server, tools)
    existing = set(allow)
    missing = [w for w in wanted if w not in existing]
    changed = bool(missing)
    allow.extend(missing)

    if workspace is not None and _is_safe_workspace(workspace, Path.home()):
        tw = cfg.setdefault("trustedWorkspaces", [])
        if isinstance(tw, list):
            ws = str(Path(workspace))
            if ws not in tw:
                tw.append(ws)
                changed = True

    if not changed:
        return Result(label, "already", "daimon tools already whitelisted")
    _atomic_write(path, cfg, backup=True, ts=ts)
    return Result(label, "installed", str(path))


def uninstall_agy_permissions(label: str, path: Path, server: str, *, ts: str = "0") -> Result:
    """Remove every ``mcp(server/<tool>)`` entry from a surface's
    ``permissions.allow`` (reversible). Leaves trustedWorkspaces alone — other
    servers may rely on the trusted dir.
    """
    try:
        cfg = read_config(path)
    except ValueError as e:
        return Result(label, "error", f"malformed config: {e}")
    perms = cfg.get("permissions")
    if not isinstance(perms, dict) or not isinstance(perms.get("allow"), list):
        return Result(label, "absent", "daimon not whitelisted")
    prefix = f"mcp({server}/"
    allow = perms["allow"]
    kept = [a for a in allow if not (isinstance(a, str) and a.startswith(prefix))]
    if len(kept) == len(allow):
        return Result(label, "absent", "daimon not whitelisted")
    perms["allow"] = kept
    _atomic_write(path, cfg, backup=True, ts=ts)
    return Result(label, "removed", str(path))


def status_agy_permissions(label: str, path: Path, server: str, tools) -> Result:
    """Report whether every daimon tool is whitelisted in a surface's settings.json."""
    try:
        cfg = read_config(path)
    except ValueError:
        return Result(label, "error", "malformed config")
    perms = cfg.get("permissions", {})
    allow = perms.get("allow", []) if isinstance(perms, dict) else []
    present = isinstance(allow, list) and set(agy_tool_perms(server, tools)) <= set(allow)
    return Result(label, "present" if present else "absent", str(path))
