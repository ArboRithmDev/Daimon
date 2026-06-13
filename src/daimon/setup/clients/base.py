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
    name: str
    config_path: Path
    key: str = "mcpServers"
    detect_paths: tuple[Path, ...] = ()
    fmt: str = "json"   # json | toml-table | toml-array

    def detect(self) -> bool:
        paths = self.detect_paths or (self.config_path,)
        return any(Path(p).exists() for p in paths)


@dataclass(frozen=True)
class Result:
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


def install(adapter: ClientAdapter, name: str, entry: dict, *, ts: str = "0") -> Result:
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
        return Result(adapter.name, "already", "daimon already registered")
    servers[name] = entry
    _atomic_write(adapter.config_path, cfg, backup=True, ts=ts)
    return Result(adapter.name, "installed", str(adapter.config_path))


def uninstall(adapter: ClientAdapter, name: str, *, ts: str = "0") -> Result:
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
    return Result(adapter.name, "removed", str(adapter.config_path))


def status(adapter: ClientAdapter, name: str) -> Result:
    if adapter.fmt in ("toml-table", "toml-array"):
        return _status_toml(adapter)
    try:
        cfg = read_config(adapter.config_path)
    except ValueError:
        return Result(adapter.name, "error", "malformed config")
    servers = cfg.get(adapter.key, {})
    present = isinstance(servers, dict) and name in servers
    return Result(adapter.name, "present" if present else "absent", str(adapter.config_path))
