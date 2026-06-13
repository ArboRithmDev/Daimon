# Phase 2 — Auto-install + Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** Take a non-technical user from "installed Daimon" to "my AI sees and acts" without a terminal — auto-register Daimon into each AI client's MCP config (idempotent, reversible) and guide the macOS permission grants with live verification.

**Architecture:** A pure core (client-config JSON merge, command resolution, permission status model, wizard state machine) under two thin front-ends (premium CLI + AppKit GUI). macOS permission calls sit behind an injectable `PermissionBackend`; the GUI is smoke-only. Everything pure is unit-tested.

**Tech Stack:** Python 3.12, stdlib (json/shutil/subprocess/argparse), pyobjc (permissions + GUI, deferred), pytest.

---

## File structure

| File | Responsibility |
|------|----------------|
| `src/daimon/setup/__init__.py` | package doc |
| `src/daimon/setup/clients/base.py` | `ClientAdapter` + idempotent JSON merge install/uninstall/status, backup, atomic write |
| `src/daimon/setup/clients/registry.py` | the adapter list (Claude Code/Desktop/Cursor/Windsurf/generic) |
| `src/daimon/setup/invocation.py` | resolve the `daimon` command to register |
| `src/daimon/setup/permissions.py` | `PermissionBackend`/`FakeBackend`/`MacOSBackend`, `permissions_status` |
| `src/daimon/setup/wizard.py` | `Step`, `IO`, `Wizard.run` |
| `src/daimon/setup/cli.py` | premium CLI front-end |
| `src/daimon/setup/gui/window.py`, `gui/__main__.py` | AppKit onboarding (smoke) |
| `src/daimon/__main__.py` | dispatch: no-arg → server; subcommand → CLI |
| `src/daimon/onboard.py` | `python -m daimon.onboard` (permissions wizard, --gui) |
| `tests/test_setup_*` | per task |

Order: clients/base → registry → invocation → permissions → wizard → cli → dispatch+onboard → GUI → smoke+docs.

---

## Task 1: Client config merge (pure + fs)

**Files:** Create `src/daimon/setup/__init__.py`, `src/daimon/setup/clients/__init__.py`, `src/daimon/setup/clients/base.py`, `tests/test_setup_clients.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_setup_clients.py
import json
import pytest
from daimon.setup.clients.base import ClientAdapter, install, uninstall, status, read_config


def _adapter(tmp_path, name="Test"):
    return ClientAdapter(name=name, config_path=tmp_path / "cfg.json")


ENTRY = {"command": "daimon", "args": [], "env": {}}


def test_install_creates_entry_and_backup(tmp_path):
    a = _adapter(tmp_path)
    r = install(a, "daimon", ENTRY)
    assert r.action == "installed"
    data = json.loads(a.config_path.read_text())
    assert data["mcpServers"]["daimon"] == ENTRY


def test_install_is_idempotent(tmp_path):
    a = _adapter(tmp_path)
    install(a, "daimon", ENTRY)
    r = install(a, "daimon", ENTRY)
    assert r.action == "already"


def test_install_preserves_other_servers_and_backs_up(tmp_path):
    a = _adapter(tmp_path)
    a.config_path.write_text(json.dumps({"mcpServers": {"other": {"command": "x"}}, "misc": 1}))
    install(a, "daimon", ENTRY)
    data = json.loads(a.config_path.read_text())
    assert data["mcpServers"]["other"] == {"command": "x"}
    assert data["misc"] == 1
    assert (tmp_path / "cfg.json.bak").exists() or any(p.name.startswith("cfg.json.bak") for p in tmp_path.iterdir())


def test_malformed_json_is_refused_not_overwritten(tmp_path):
    a = _adapter(tmp_path)
    a.config_path.write_text("{ not json")
    r = install(a, "daimon", ENTRY)
    assert r.action == "error"
    assert a.config_path.read_text() == "{ not json"  # untouched


def test_uninstall_removes_only_daimon(tmp_path):
    a = _adapter(tmp_path)
    a.config_path.write_text(json.dumps({"mcpServers": {"daimon": ENTRY, "other": {"command": "x"}}}))
    r = uninstall(a, "daimon")
    assert r.action == "removed"
    data = json.loads(a.config_path.read_text())
    assert "daimon" not in data["mcpServers"] and "other" in data["mcpServers"]


def test_status_reports_presence(tmp_path):
    a = _adapter(tmp_path)
    assert status(a, "daimon").action == "absent"
    install(a, "daimon", ENTRY)
    assert status(a, "daimon").action == "present"
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement**

`src/daimon/setup/__init__.py`:
```python
"""Setup — auto-install into AI clients and guided macOS onboarding.

A pure core (config merge, command resolution, permission model, wizard) under
thin CLI/GUI front-ends. Never corrupts another tool's config: backup + atomic
write + refusal on malformed JSON. Idempotent and reversible.
"""
```
`src/daimon/setup/clients/__init__.py`: `"""AI-client adapters and idempotent MCP-config registration."""`

`src/daimon/setup/clients/base.py`:
```python
"""Client adapter + idempotent, reversible, safe MCP-config registration."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class ClientAdapter:
    name: str
    config_path: Path
    key: str = "mcpServers"
    detect_paths: tuple[Path, ...] = ()

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


def install(adapter: ClientAdapter, name: str, entry: dict, *, ts: str = "0") -> Result:
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
    try:
        cfg = read_config(adapter.config_path)
    except ValueError:
        return Result(adapter.name, "error", "malformed config")
    servers = cfg.get(adapter.key, {})
    present = isinstance(servers, dict) and name in servers
    return Result(adapter.name, "present" if present else "absent", str(adapter.config_path))
```

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(setup): idempotent reversible client MCP-config registration"`

---

## Task 2: Client registry

**Files:** Create `src/daimon/setup/clients/registry.py`, `tests/test_setup_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_setup_registry.py
from pathlib import Path
from daimon.setup.clients.registry import adapters_for_home, detected


def test_adapters_cover_known_clients():
    home = Path("/Users/test")
    names = {a.name for a in adapters_for_home(home)}
    assert {"Claude Code", "Claude Desktop", "Cursor", "Windsurf"} <= names


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
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `src/daimon/setup/clients/registry.py`:
```python
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
```

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(setup): client registry (Claude Code/Desktop/Cursor/Windsurf)"`

---

## Task 3: Daimon command resolution

**Files:** Create `src/daimon/setup/invocation.py`, `tests/test_setup_invocation.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_setup_invocation.py
from daimon.setup import invocation


def test_uses_console_script_when_present(monkeypatch):
    monkeypatch.setattr(invocation.shutil, "which", lambda n: "/usr/local/bin/daimon")
    entry = invocation.daimon_command()
    assert entry["command"] == "/usr/local/bin/daimon"
    assert entry["args"] == []
    assert entry["env"] == {}


def test_falls_back_to_python_module(monkeypatch):
    monkeypatch.setattr(invocation.shutil, "which", lambda n: None)
    monkeypatch.setattr(invocation.sys, "executable", "/opt/py/bin/python3.12")
    entry = invocation.daimon_command()
    assert entry["command"] == "/opt/py/bin/python3.12"
    assert entry["args"] == ["-m", "daimon"]
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `src/daimon/setup/invocation.py`:
```python
"""Resolve the command an MCP client should run to start Daimon.

Prefer an installed `daimon` console script; fall back to `python -m daimon`
with the current interpreter so it works from a venv/source checkout too."""

from __future__ import annotations

import shutil
import sys


def daimon_command() -> dict:
    exe = shutil.which("daimon")
    if exe:
        return {"command": exe, "args": [], "env": {}}
    return {"command": sys.executable, "args": ["-m", "daimon"], "env": {}}
```

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(setup): resolve daimon invocation (console-script | python -m)"`

---

## Task 4: Permissions backend + status

**Files:** Create `src/daimon/setup/permissions.py`, `tests/test_setup_permissions.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_setup_permissions.py
from daimon.setup.permissions import FakeBackend, permissions_status, PANE_ACCESSIBILITY


def test_status_reflects_backend():
    b = FakeBackend(screen=True, accessibility=False)
    perms = {p.key: p for p in permissions_status(b)}
    assert perms["screen_recording"].granted is True
    assert perms["accessibility"].granted is False
    assert "Accessibility" in perms["accessibility"].label


def test_open_pane_and_request_recorded():
    b = FakeBackend(screen=False, accessibility=False)
    b.request_accessibility()
    b.open_pane(PANE_ACCESSIBILITY)
    assert b.requested == ["accessibility"]
    assert b.opened == [PANE_ACCESSIBILITY]


def test_all_granted_helper():
    assert all(p.granted for p in permissions_status(FakeBackend(screen=True, accessibility=True)))
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `src/daimon/setup/permissions.py`:
```python
"""macOS permission status + guidance. We never *grant* TCC (impossible by
design); we detect, trigger the system prompt, open the right Settings pane, and
verify. Calls are behind a backend so the model is testable without macOS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

PANE_SCREEN = "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"
PANE_ACCESSIBILITY = "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"


@dataclass(frozen=True)
class Permission:
    key: str
    label: str
    granted: bool
    pane: str
    how_to: str


class PermissionBackend(Protocol):
    def screen_recording_ok(self) -> bool: ...
    def accessibility_ok(self) -> bool: ...
    def request_screen_recording(self) -> None: ...
    def request_accessibility(self) -> None: ...
    def open_pane(self, pane: str) -> None: ...


class FakeBackend:
    def __init__(self, screen=False, accessibility=False):
        self._screen = screen
        self._acc = accessibility
        self.requested: list[str] = []
        self.opened: list[str] = []
    def screen_recording_ok(self): return self._screen
    def accessibility_ok(self): return self._acc
    def request_screen_recording(self): self.requested.append("screen")
    def request_accessibility(self): self.requested.append("accessibility")
    def open_pane(self, pane): self.opened.append(pane)


class MacOSBackend:
    def screen_recording_ok(self) -> bool:
        from Quartz import CGPreflightScreenCaptureAccess
        return bool(CGPreflightScreenCaptureAccess())
    def accessibility_ok(self) -> bool:
        from ApplicationServices import AXIsProcessTrusted
        return bool(AXIsProcessTrusted())
    def request_screen_recording(self) -> None:
        from Quartz import CGRequestScreenCaptureAccess
        CGRequestScreenCaptureAccess()
    def request_accessibility(self) -> None:
        from ApplicationServices import AXIsProcessTrustedWithOptions
        from CoreFoundation import CFDictionaryCreate, kCFTypeDictionaryKeyCallBacks, kCFTypeDictionaryValueCallBacks
        # kAXTrustedCheckOptionPrompt == "AXTrustedCheckOptionPrompt"
        try:
            AXIsProcessTrustedWithOptions({"AXTrustedCheckOptionPrompt": True})
        except Exception:
            from ApplicationServices import AXIsProcessTrusted
            AXIsProcessTrusted()
    def open_pane(self, pane: str) -> None:
        import subprocess
        subprocess.run(["open", pane], check=False)


def permissions_status(backend: PermissionBackend) -> list[Permission]:
    return [
        Permission("screen_recording", "Screen Recording (Vue)", backend.screen_recording_ok(),
                   PANE_SCREEN, "Lets Daimon see your screen."),
        Permission("accessibility", "Accessibility (Touché + Hands)", backend.accessibility_ok(),
                   PANE_ACCESSIBILITY, "Lets Daimon read UI structure and act."),
    ]
```

- [ ] **Step 4: Run, expect PASS.** `import daimon.setup.permissions` clean.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(setup): permission status model + macOS/fake backends"`

---

## Task 5: Wizard engine

**Files:** Create `src/daimon/setup/wizard.py`, `tests/test_setup_wizard.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_setup_wizard.py
from daimon.setup.wizard import Step, Wizard, RecordingIO


def test_already_satisfied_step_is_skipped():
    io = RecordingIO()
    done = {"x": True}
    s = Step(id="x", title="X", check=lambda: done["x"], act=lambda: io.say("acting"), guidance="g")
    assert Wizard([s]).run(io) is True
    assert "acting" not in "\n".join(io.lines)


def test_pending_step_acts_then_verifies():
    io = RecordingIO()
    flips = {"n": 0}
    def check():
        flips["n"] += 1
        return flips["n"] >= 3   # becomes true on the 3rd check (after act + polls)
    acted = []
    s = Step(id="p", title="Grant", check=check, act=lambda: acted.append(True), guidance="do it")
    ok = Wizard([s]).run(io, max_polls=5)
    assert ok is True and acted == [True]


def test_never_satisfied_gives_up():
    io = RecordingIO()
    s = Step(id="p", title="Grant", check=lambda: False, act=lambda: None, guidance="g")
    assert Wizard([s]).run(io, max_polls=3) is False


def test_steps_run_in_order():
    io = RecordingIO()
    order = []
    steps = [Step(id=str(i), title=f"S{i}", check=lambda: True,
                  act=lambda: None, guidance="") for i in range(3)]
    Wizard(steps).run(io)
    assert [l for l in io.lines if l.startswith("STEP")] == ["STEP S0", "STEP S1", "STEP S2"]
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `src/daimon/setup/wizard.py`:
```python
"""Pure onboarding wizard engine: ordered steps with check()/act()/verify, over
an injected IO so both the CLI and GUI front-ends reuse one logic."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol


@dataclass
class Step:
    id: str
    title: str
    check: Callable[[], bool]
    act: Callable[[], None]
    guidance: str = ""


class IO(Protocol):
    def say(self, message: str) -> None: ...
    def wait(self, seconds: float) -> None: ...


class RecordingIO:
    """Test IO: records lines, wait() is a no-op."""
    def __init__(self): self.lines: list[str] = []
    def say(self, message: str) -> None: self.lines.append(message)
    def wait(self, seconds: float) -> None: pass


class Wizard:
    def __init__(self, steps: list[Step]) -> None:
        self._steps = steps

    def run(self, io: IO, *, max_polls: int = 30, poll_seconds: float = 1.0) -> bool:
        all_ok = True
        for step in self._steps:
            io.say(f"STEP {step.title}")
            if step.check():
                io.say(f"OK {step.title}")
                continue
            if step.guidance:
                io.say(step.guidance)
            step.act()
            satisfied = False
            for _ in range(max_polls):
                if step.check():
                    satisfied = True
                    break
                io.wait(poll_seconds)
            io.say(("OK " if satisfied else "PENDING ") + step.title)
            all_ok = all_ok and satisfied
        return all_ok
```

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(setup): pure wizard engine (check/act/verify over injected IO)"`

---

## Task 6: CLI front-end

**Files:** Create `src/daimon/setup/cli.py`, `tests/test_setup_cli.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_setup_cli.py
from daimon.setup.cli import run_command
from daimon.setup.clients.base import ClientAdapter


def _adapters(tmp_path):
    a = ClientAdapter("Test", tmp_path / "a.json")
    a.config_path.write_text("{}")   # detected
    return [a]


def test_status_runs(tmp_path, capsys):
    code = run_command(["status"], adapters=_adapters(tmp_path))
    assert code == 0
    assert "Test" in capsys.readouterr().out


def test_install_then_uninstall(tmp_path, capsys):
    ad = _adapters(tmp_path)
    assert run_command(["install", "--all"], adapters=ad) == 0
    import json
    assert "daimon" in json.loads((tmp_path / "a.json").read_text())["mcpServers"]
    assert run_command(["uninstall", "--all"], adapters=ad) == 0
    assert "daimon" not in json.loads((tmp_path / "a.json").read_text()).get("mcpServers", {})


def test_unknown_command_returns_nonzero(tmp_path):
    assert run_command(["frobnicate"], adapters=_adapters(tmp_path)) != 0
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `src/daimon/setup/cli.py`:
```python
"""Premium CLI front-end: daimon install|uninstall|status|onboard|setup.

Thin over the pure core (registry + invocation + wizard + permissions). Backends
are injectable so the whole CLI is testable without touching real configs or
macOS."""

from __future__ import annotations

import sys

from .clients import base
from .clients.registry import default_adapters, detected
from .invocation import daimon_command

_OK = "\033[32m"; _WARN = "\033[33m"; _DIM = "\033[2m"; _END = "\033[0m"


def _ts() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _print(msg: str) -> None:
    print(msg)


def _targets(adapters):
    adapters = adapters if adapters is not None else default_adapters()
    return detected(adapters)


def cmd_status(adapters) -> int:
    for a in _targets(adapters):
        r = base.status(a, "daimon")
        tag = f"{_OK}registered{_END}" if r.action == "present" else f"{_DIM}not registered{_END}"
        _print(f"  {a.name:16} {tag}  {_DIM}{a.config_path}{_END}")
    return 0


def cmd_install(adapters) -> int:
    entry = daimon_command()
    ts = _ts()
    for a in _targets(adapters):
        r = base.install(a, "daimon", entry, ts=ts)
        _print(f"  {a.name:16} {r.action}  {_DIM}{r.detail}{_END}")
    return 0


def cmd_uninstall(adapters) -> int:
    ts = _ts()
    for a in _targets(adapters):
        r = base.uninstall(a, "daimon", ts=ts)
        _print(f"  {a.name:16} {r.action}")
    return 0


def run_command(argv, *, adapters=None, backend=None, io=None) -> int:
    if not argv:
        _print("Usage: daimon [setup|install|uninstall|status|onboard]")
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "status":
        return cmd_status(adapters)
    if cmd == "install":
        return cmd_install(adapters)
    if cmd == "uninstall":
        return cmd_uninstall(adapters)
    if cmd in ("onboard", "setup"):
        from .onboard_flow import run_onboarding
        rc = 0
        if cmd == "setup":
            rc = cmd_install(adapters)
        return rc or run_onboarding(backend=backend, io=io)
    _print(f"Unknown command: {cmd}")
    return 2
```

Also create `src/daimon/setup/onboard_flow.py` (the shared onboarding flow used by CLI `onboard`/`setup` and `python -m daimon.onboard`):
```python
"""Build and run the permission onboarding wizard (front-end-agnostic)."""

from __future__ import annotations

from .permissions import MacOSBackend, permissions_status, Permission
from .wizard import IO, Step, Wizard


class ConsoleIO:
    def say(self, message: str) -> None:
        print(message)
    def wait(self, seconds: float) -> None:
        import time
        time.sleep(seconds)


def _step_for(backend, perm: Permission) -> Step:
    def act():
        if perm.key == "screen_recording":
            backend.request_screen_recording()
        else:
            backend.request_accessibility()
        backend.open_pane(perm.pane)
    def check():
        return {p.key: p.granted for p in permissions_status(backend)}[perm.key]
    return Step(id=perm.key, title=perm.label, check=check, act=act,
                guidance=f"{perm.how_to} Grant it in the window that opens, then I'll verify.")


def build_wizard(backend) -> Wizard:
    return Wizard([_step_for(backend, p) for p in permissions_status(backend)])


def run_onboarding(*, backend=None, io: IO | None = None, max_polls: int = 30) -> int:
    backend = backend or MacOSBackend()
    io = io or ConsoleIO()
    ok = build_wizard(backend).run(io, max_polls=max_polls)
    io.say("Daimon is ready." if ok else "Some permissions are still missing — re-run `daimon onboard`.")
    return 0 if ok else 1
```

(Update the test for `onboard`/`setup` is covered by wizard/permissions tests; CLI test only covers status/install/uninstall to avoid real macOS.)

- [ ] **Step 4: Run, expect PASS.** Full suite green. `import daimon.setup.cli, daimon.setup.onboard_flow` clean.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(setup): premium CLI (install/uninstall/status) + onboarding flow"`

---

## Task 7: Dispatch + onboard module + console entry

**Files:** Modify `src/daimon/__main__.py`, Create `src/daimon/onboard.py`, Test `tests/test_main_dispatch.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_main_dispatch.py
import daimon.__main__ as m


def test_subcommand_routes_to_cli(monkeypatch):
    calls = {}
    monkeypatch.setattr("daimon.setup.cli.run_command", lambda argv: calls.setdefault("argv", argv) or 0)
    code = m.main(["status"])
    assert calls["argv"] == ["status"] and code == 0


def test_no_arg_runs_server(monkeypatch):
    ran = {}
    monkeypatch.setattr("daimon.server.main", lambda: ran.setdefault("server", True))
    m.main([])
    assert ran.get("server") is True
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `src/daimon/__main__.py`:
```python
"""Entrypoint: `python -m daimon` (MCP server) or `daimon <subcommand>` (setup).

No-arg keeps the long-standing behaviour MCP clients rely on: start the stdio
server. A known subcommand routes to the setup CLI instead."""

from __future__ import annotations

import sys

_SUBCOMMANDS = {"setup", "install", "uninstall", "status", "onboard"}


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] in _SUBCOMMANDS:
        from .setup.cli import run_command
        return run_command(argv)
    from .server import main as server_main
    server_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```
`src/daimon/onboard.py`:
```python
"""`python -m daimon.onboard` — guided permission onboarding (CLI, or --gui)."""

from __future__ import annotations

import sys


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--gui" in argv:
        from .setup.gui.__main__ import main as gui_main
        return gui_main()
    from .setup.onboard_flow import run_onboarding
    return run_onboarding()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run, expect PASS.** Full suite green. Confirm `daimon` no-arg still starts the server (the dispatch test mocks it).
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(setup): __main__ dispatch (server vs subcommands) + onboard module"`

---

## Task 8: GUI onboarding window (macOS, smoke)

**Files:** Create `src/daimon/setup/gui/__init__.py`, `gui/window.py`, `gui/__main__.py`

No unit tests (AppKit). Acceptance = clean bare import (deferred macOS imports) + the window drives the same `build_wizard`/permissions core.

- [ ] **Step 1:** `src/daimon/setup/gui/__init__.py`: `"""AppKit onboarding window (premium, smoke-only)."""`

- [ ] **Step 2:** `src/daimon/setup/gui/window.py` — a simple premium panel listing permissions with live status dots and "Grant" buttons, plus a "Done" enabled when all granted. Keep all AppKit imports inside methods:
```python
"""Premium onboarding window: permission rows with live status + Grant buttons."""

from __future__ import annotations


class OnboardingController:
    def __init__(self, backend):
        self._backend = backend
        self._rows = {}
        self._window = None

    def show(self):
        from AppKit import (
            NSWindow, NSWindowStyleMaskTitled, NSWindowStyleMaskClosable,
            NSBackingStoreBuffered, NSMakeRect, NSTextField, NSButton, NSColor,
        )
        from .layout import build_panel  # tiny helper for premium spacing
        rect = NSMakeRect(0, 0, 460, 260)
        win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            rect, NSWindowStyleMaskTitled | NSWindowStyleMaskClosable, NSBackingStoreBuffered, False)
        win.setTitle_("Daimon — Setup")
        win.center()
        build_panel(self, win.contentView())
        win.makeKeyAndOrderFront_(None)
        self._window = win
        self._start_poll()

    def grant(self, key):
        from .permissions import PANE_SCREEN, PANE_ACCESSIBILITY  # noqa
        if key == "screen_recording":
            self._backend.request_screen_recording()
        else:
            self._backend.request_accessibility()
        from ..permissions import PANE_SCREEN as PS, PANE_ACCESSIBILITY as PA
        self._backend.open_pane(PS if key == "screen_recording" else PA)

    def _start_poll(self):
        from PyObjCTools import AppHelper
        from ..permissions import permissions_status
        def tick():
            for p in permissions_status(self._backend):
                self._update_row(p)
            AppHelper.callLater(1.0, tick)
        tick()

    def _update_row(self, perm):
        row = self._rows.get(perm.key)
        if row is not None:
            row["dot"].setStringValue_("🟢" if perm.granted else "⚪️")

    # build_panel/_update_row wire NSTextField rows + NSButton(target=self, action="grant:")
```
(`gui/layout.py` is a tiny helper creating NSTextField rows + buttons with premium spacing; keep AppKit imports inside it.)

- [ ] **Step 3:** `src/daimon/setup/gui/__main__.py`:
```python
"""GUI onboarding entry."""

from __future__ import annotations


def main() -> int:
    from AppKit import NSApplication, NSApplicationActivationPolicyRegular
    from PyObjCTools import AppHelper
    from ..permissions import MacOSBackend
    from .window import OnboardingController
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    OnboardingController(MacOSBackend()).show()
    app.activateIgnoringOtherApps_(True)
    AppHelper.runEventLoop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4:** Verify bare imports: `PYTHONPATH=src python -c "import daimon.setup.gui.window, daimon.setup.gui.__main__"` (must succeed with no AppKit at module top level). Full suite green. The implementer should create the small `gui/layout.py` helper too, keeping all AppKit imports inside functions.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(setup): macOS GUI onboarding window (premium, smoke-only)"`

---

## Task 9: Smoke + docs

**Files:** Create `scripts/smoke_setup.py`, Modify `README.md`, run suite

- [ ] **Step 1:** `scripts/smoke_setup.py` — print `daimon status` then a dry-run summary of what `install` would write (uses the real registry + invocation, but prints the entry instead of writing). Helps verify detection on the real Mac.
- [ ] **Step 2:** Run full suite — all pass.
- [ ] **Step 3:** README — add "## Setup (install + onboarding)": one-liner `daimon setup` does it all (registers Daimon into detected AI clients, then guides macOS permissions with live verification); subcommands `daimon install|uninstall|status|onboard`; GUI via `python -m daimon.onboard --gui`; `daimon` with no args is still the MCP server; everything idempotent, reversible, backed up.
- [ ] **Step 4:** Commit — `git add -A && git commit -m "docs: setup (auto-install + guided onboarding); smoke script"`

---

## Self-review

- **Spec coverage:** D auto-install → clients/base (T1) + registry (T2) + invocation (T3) + cli (T6); G onboarding → permissions (T4) + wizard (T5) + onboard_flow (T6) + GUI (T8); dispatch/back-compat → T7; smoke/docs → T9. ✓
- **Placeholders:** GUI `window.py`/`layout.py` are described as premium-but-thin; the implementer fills the NSTextField/NSButton wiring — this is the one inherently-untestable surface (documented). All pure code is complete.
- **Type consistency:** `ClientAdapter`/`Result` used across base/registry/cli (T1/T2/T6); `daimon_command()` entry dict shape consistent (T3/T6); `permissions_status`/`Permission`/backends consistent across permissions/onboard_flow/gui (T4/T6/T8); `Wizard.run(io, max_polls=...)` signature consistent (T5/T6). ✓
- **Invariants:** never-corrupt (backup + atomic + malformed-refusal) in T1 tests; idempotent/reversible in T1; honest-TCC (no grant, only detect/request/open/verify) in T4/T5; one logic two front-ends (onboard_flow + wizard reused by CLI and GUI) T6/T8; back-compat (no-arg server) T7. ✓
