# Phase 1 — Overlay (the face) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** Add the "show" organ — a premium, click-through, capture-invisible overlay that highlights what the agent looks at and acts on, and emphasises the exact element the human confirms at the gate.

**Architecture:** A separate long-lived overlay helper process (`python -m daimon.overlay.app`) owns the AppKit run loop and draws with Core Animation layers; the MCP server talks to it over a Unix-socket JSON line protocol via an injected `Presenter` (default `NullPresenter`, so the motor core stays pure and testable). The overlay window is `ignoresMouseEvents` + `NSWindowSharingNone` (click-through + invisible to Vue capture). All pure logic (protocol, theme, presenter, client, launcher, label redaction) is unit-tested; the AppKit GUI is thin and smoke-validated.

**Tech Stack:** Python 3.12, pyobjc (AppKit/Quartz/CoreAnimation), asyncio, FastMCP, pytest.

---

## File structure

| File | Responsibility |
|------|----------------|
| `src/daimon/overlay/__init__.py` | package doc |
| `src/daimon/overlay/protocol.py` | PURE command dataclasses ↔ JSON lines |
| `src/daimon/overlay/theme.py` | PURE level/style → colour/radius/duration |
| `src/daimon/overlay/presenter.py` | `Presenter` protocol, `NullPresenter`, `RecordingPresenter`, `OverlayPresenter` (motor cycle → commands + label redaction) |
| `src/daimon/overlay/client.py` | `OverlayClient` — send command lines, silent-fail/buffer, reconnect |
| `src/daimon/overlay/launcher.py` | socket path + auto-spawn-if-not-running |
| `src/daimon/overlay/app/__main__.py` | overlay process entry (NSApplication + socket server) |
| `src/daimon/overlay/app/window.py` | transparent click-through capture-invisible NSWindow |
| `src/daimon/overlay/app/scene.py` | CALayer scene + animations |
| `src/daimon/overlay/app/server.py` | socket read loop applying commands on the main thread |
| `src/daimon/motor/organ.py` | optional `presenter`, lifecycle calls |
| `src/daimon/config.py` | `OverlayConfig` |
| `src/daimon/server.py` | wire `OverlayPresenter`; register `overlay_*` tools |
| `scripts/smoke_overlay.py` | launch + send a demo sequence |

Order: protocol → theme → presenter → client → launcher → organ → config → GUI → server/smoke → docs.

---

## Task 1: Command protocol (pure)

**Files:** Create `src/daimon/overlay/__init__.py`, `src/daimon/overlay/protocol.py`, `tests/test_overlay_protocol.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_overlay_protocol.py
from daimon.overlay.protocol import (
    Highlight, Spotlight, Cursor, Ripple, Banner, Clear, encode, decode,
)


def test_highlight_round_trip():
    h = Highlight(x=10, y=20, w=80, h=30, label='AXButton "Send"', style="gate")
    line = encode(h)
    assert isinstance(line, str) and line.endswith("\n")
    back = decode(line)
    assert isinstance(back, Highlight) and back.label == 'AXButton "Send"' and back.style == "gate"


def test_each_command_encodes_its_cmd_tag():
    assert '"cmd": "ripple"' in encode(Ripple(x=1, y=2)) or '"cmd":"ripple"' in encode(Ripple(x=1, y=2))
    assert decode(encode(Banner(text="hi", level="L2"))).text == "hi"
    assert isinstance(decode(encode(Clear())), Clear)
    assert decode(encode(Spotlight(x=0, y=0, w=5, h=5))).w == 5
    assert decode(encode(Cursor(x=3, y=4))).y == 4


def test_decode_unknown_cmd_raises():
    import pytest
    with pytest.raises(ValueError):
        decode('{"cmd": "nope"}')
```

- [ ] **Step 2: Run, expect FAIL** — `PYTHONPATH=src python -m pytest tests/test_overlay_protocol.py -v`.

- [ ] **Step 3: Implement**

`src/daimon/overlay/__init__.py`:
```python
"""Overlay — Daimon's "show" organ.

A separate helper process draws a premium, click-through, capture-invisible
overlay; the MCP server drives it over a Unix-socket JSON protocol via an
injected Presenter. Purely presentational: it never acts, never intercepts
input, never leaks secret content, and is never on an action's critical path.
"""
```

`src/daimon/overlay/protocol.py`:
```python
"""Pure overlay command protocol — dataclasses ↔ newline-delimited JSON.

No macOS imports: the same commands are produced on the MCP-server side and
consumed in the overlay process. One JSON object per line; `cmd` tags the type.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class Highlight:
    x: int; y: int; w: int; h: int
    label: str = ""
    style: str = "default"   # default|L1|L2|L3|gate
    cmd: str = field(default="highlight", init=False)


@dataclass(frozen=True)
class Spotlight:
    x: int; y: int; w: int; h: int
    cmd: str = field(default="spotlight", init=False)


@dataclass(frozen=True)
class Cursor:
    x: int; y: int
    cmd: str = field(default="cursor", init=False)


@dataclass(frozen=True)
class Ripple:
    x: int; y: int
    cmd: str = field(default="ripple", init=False)


@dataclass(frozen=True)
class Banner:
    text: str
    level: str = "L1"
    cmd: str = field(default="banner", init=False)


@dataclass(frozen=True)
class Clear:
    cmd: str = field(default="clear", init=False)


_BY_CMD = {c().cmd if c is Clear else c.__dataclass_fields__["cmd"].default: c
           for c in (Highlight, Spotlight, Cursor, Ripple, Banner, Clear)}


def encode(command) -> str:
    return json.dumps(asdict(command), ensure_ascii=False) + "\n"


def decode(line: str):
    data = json.loads(line)
    cmd = data.pop("cmd", None)
    klass = _BY_CMD.get(cmd)
    if klass is None:
        raise ValueError(f"unknown overlay command: {cmd!r}")
    return klass(**data)
```

- [ ] **Step 4: Run, expect PASS.**

- [ ] **Step 5: Commit** — `git add src/daimon/overlay/__init__.py src/daimon/overlay/protocol.py tests/test_overlay_protocol.py && git commit -m "feat(overlay): pure command protocol (dataclasses <-> JSON lines)"`

---

## Task 2: Theme (pure)

**Files:** Create `src/daimon/overlay/theme.py`, `tests/test_overlay_theme.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_overlay_theme.py
from daimon.overlay.theme import style_for, STYLES


def test_known_styles_have_color_and_duration():
    for style in ["default", "L1", "L2", "L3", "gate"]:
        s = style_for(style)
        assert "rgba" in s and "duration" in s and "radius" in s
        assert len(s["rgba"]) == 4


def test_gate_is_red_and_pulses():
    s = style_for("gate")
    r, g, b, a = s["rgba"]
    assert r > 0.7 and g < 0.4 and b < 0.4  # red
    assert s["pulse"] is True


def test_unknown_style_falls_back_to_default():
    assert style_for("???") == STYLES["default"]
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `src/daimon/overlay/theme.py`:
```python
"""Pure visual theme — maps a style/level to colour, corner radius, animation.

RGBA components are 0..1 floats (Core Animation / NSColor friendly). One
carefully-tuned premium palette; levels are colour-coded by escalation."""

from __future__ import annotations

STYLES: dict[str, dict] = {
    "default": {"rgba": (0.60, 0.64, 0.70, 0.90), "radius": 8, "duration": 0.25, "pulse": False},
    "L1":      {"rgba": (0.55, 0.60, 0.66, 0.85), "radius": 8, "duration": 0.25, "pulse": False},
    "L2":      {"rgba": (0.25, 0.55, 0.95, 0.95), "radius": 8, "duration": 0.22, "pulse": False},
    "L3":      {"rgba": (0.96, 0.70, 0.20, 0.97), "radius": 9, "duration": 0.20, "pulse": True},
    "gate":    {"rgba": (0.92, 0.23, 0.23, 1.00), "radius": 10, "duration": 0.16, "pulse": True},
}


def style_for(name: str) -> dict:
    return STYLES.get(name, STYLES["default"])
```

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(overlay): pure premium theme (level-coded colours/animation)"`

---

## Task 3: Presenter (protocol + Null + Recording + Overlay)

**Files:** Create `src/daimon/overlay/presenter.py`, `tests/test_overlay_presenter.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_overlay_presenter.py
from daimon.config import ExclusionConfig
from daimon.exclusions import ExclusionFilter
from daimon.overlay.presenter import NullPresenter, RecordingPresenter, OverlayPresenter
from daimon.overlay.protocol import Highlight, Banner, Ripple
from daimon.motor.types import Declaration, Decision, Level, MotorAction, Target, Verdict


def _action(label, role="AXButton", x=10, y=20):
    return MotorAction(name="click", level=Level.INPUT,
                       target=Target(role=role, label=label, x=x, y=y, observed=True),
                       declaration=Declaration(reversible=True, intent="submit the form"),
                       params={"x": x, "y": y})


class _Sink:
    def __init__(self): self.lines = []
    def send(self, command): self.lines.append(command)


def test_null_presenter_is_noop():
    p = NullPresenter()
    p.present_intent(_action("Send"), Decision(Verdict.ALLOW, "ok"))  # must not raise
    p.present_gate(_action("Send")); p.present_executed(_action("Send"), {}); p.present_refused(_action("Send"), "x")


def test_overlay_presenter_emits_highlight_and_banner_on_intent():
    sink = _Sink()
    p = OverlayPresenter(sink, ExclusionFilter(ExclusionConfig()))
    p.present_intent(_action("Send"), Decision(Verdict.ALLOW, "ok"))
    kinds = [type(c) for c in sink.lines]
    assert Highlight in kinds and Banner in kinds
    hi = next(c for c in sink.lines if isinstance(c, Highlight))
    assert "Send" in hi.label and "submit the form" in next(c for c in sink.lines if isinstance(c, Banner)).text


def test_gate_uses_gate_style():
    sink = _Sink()
    p = OverlayPresenter(sink, ExclusionFilter(ExclusionConfig()))
    p.present_gate(_action("Send"))
    hi = next(c for c in sink.lines if isinstance(c, Highlight))
    assert hi.style == "gate"


def test_secret_target_label_is_redacted():
    sink = _Sink()
    f = ExclusionFilter(ExclusionConfig(secret_roles=("AXSecureTextField",)))
    p = OverlayPresenter(sink, f)
    p.present_intent(_action("hunter2", role="AXSecureTextField"), Decision(Verdict.ALLOW, "ok"))
    hi = next(c for c in sink.lines if isinstance(c, Highlight))
    assert "hunter2" not in hi.label and "🔒" in hi.label


def test_executed_emits_ripple():
    sink = _Sink()
    p = OverlayPresenter(sink, ExclusionFilter(ExclusionConfig()))
    p.present_executed(_action("Send"), {"status": "executed"})
    assert any(isinstance(c, Ripple) for c in sink.lines)
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `src/daimon/overlay/presenter.py`:
```python
"""Presenter — turns motor lifecycle events into overlay commands.

`Presenter` is the injected interface the MotorOrgan calls; `NullPresenter` is
the headless default (keeps the core testable). `OverlayPresenter` maps each
lifecycle point to protocol commands, applying the SAME secret redaction as the
senses so the overlay never displays protected content. Commands go to a `sink`
with a `.send(command)` method (the OverlayClient, or a recorder in tests).
"""

from __future__ import annotations

from typing import Protocol

from ..exclusions import ExclusionFilter
from ..motor.types import Decision, Level, MotorAction
from .protocol import Banner, Clear, Highlight, Ripple

_LEVEL_STYLE = {Level.NONDESTRUCTIVE: "L1", Level.INPUT: "L2",
                Level.VALIDATION: "L3", Level.AUTONOMOUS: "L2"}


class Presenter(Protocol):
    def present_intent(self, action: MotorAction, decision: Decision) -> None: ...
    def present_gate(self, action: MotorAction) -> None: ...
    def present_executed(self, action: MotorAction, result: dict) -> None: ...
    def present_refused(self, action: MotorAction, reason: str) -> None: ...


class NullPresenter:
    def present_intent(self, action, decision): pass
    def present_gate(self, action): pass
    def present_executed(self, action, result): pass
    def present_refused(self, action, reason): pass


class RecordingPresenter:
    """Test double recording which lifecycle points fired."""
    def __init__(self): self.calls = []
    def present_intent(self, action, decision): self.calls.append(("intent", action))
    def present_gate(self, action): self.calls.append(("gate", action))
    def present_executed(self, action, result): self.calls.append(("executed", action))
    def present_refused(self, action, reason): self.calls.append(("refused", action))


class OverlayPresenter:
    def __init__(self, sink, exclusions: ExclusionFilter) -> None:
        self._sink = sink
        self._exclusions = exclusions

    def _label(self, action: MotorAction) -> str:
        t = action.target
        if self._exclusions.is_target_secret(role=t.role):
            return "🔒 protégé"
        name = t.label or t.role or ""
        return f'{t.role or ""} "{name}"'.strip() if name else (t.role or "target")

    def _rect(self, action: MotorAction):
        t = action.target
        x = t.x if t.x is not None else 0
        y = t.y if t.y is not None else 0
        return x, y

    def _send(self, command) -> None:
        try:
            self._sink.send(command)
        except Exception:
            pass  # overlay is never on the critical path

    def present_intent(self, action, decision) -> None:
        x, y = self._rect(action)
        style = _LEVEL_STYLE.get(action.level, "default")
        self._send(Highlight(x=x - 24, y=y - 16, w=48, h=32, label=self._label(action), style=style))
        self._send(Banner(text=f"{action.name} • {action.declaration.intent}", level=style))

    def present_gate(self, action) -> None:
        x, y = self._rect(action)
        self._send(Highlight(x=x - 24, y=y - 16, w=48, h=32, label=self._label(action), style="gate"))
        self._send(Banner(text=f"CONFIRM • {action.name} • {self._label(action)}", level="L3"))

    def present_executed(self, action, result) -> None:
        x, y = self._rect(action)
        self._send(Ripple(x=x, y=y))

    def present_refused(self, action, reason) -> None:
        self._send(Banner(text=f"refused • {reason}", level="L1"))
        self._send(Clear())
```

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(overlay): Presenter (Null/Recording/Overlay) with secret-safe labels"`

---

## Task 4: OverlayClient (socket send, silent-fail)

**Files:** Create `src/daimon/overlay/client.py`, `tests/test_overlay_client.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_overlay_client.py
from daimon.overlay.client import OverlayClient
from daimon.overlay.protocol import Banner


class _FakeSock:
    def __init__(self): self.sent = b""
    def sendall(self, b): self.sent += b


def test_send_writes_encoded_line():
    c = OverlayClient(socket_path="/tmp/x.sock")
    c._sock = _FakeSock()  # pretend connected
    c.send(Banner(text="hi", level="L2"))
    assert b"hi" in c._sock.sent and c._sock.sent.endswith(b"\n")


def test_send_without_connection_is_silent(monkeypatch):
    c = OverlayClient(socket_path="/tmp/does-not-exist.sock")
    # connect will fail; send must not raise
    c.send(Banner(text="hi"))


def test_failed_send_drops_socket(monkeypatch):
    c = OverlayClient(socket_path="/tmp/x.sock")
    class _Boom:
        def sendall(self, b): raise OSError("broken pipe")
    c._sock = _Boom()
    c.send(Banner(text="hi"))   # must not raise
    assert c._sock is None       # dropped so next send retries connect
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `src/daimon/overlay/client.py`:
```python
"""OverlayClient — fire-and-forget Unix-socket sender.

Never blocks an action and never raises to the caller: if the overlay process
is absent or the pipe breaks, the command is dropped and the socket reset so the
next send retries the connection. Encoding is the pure protocol.encode."""

from __future__ import annotations

import socket

from .protocol import encode


class OverlayClient:
    def __init__(self, socket_path: str, connect_timeout: float = 0.05) -> None:
        self._path = socket_path
        self._timeout = connect_timeout
        self._sock = None

    def _ensure(self) -> None:
        if self._sock is not None:
            return
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(self._timeout)
            s.connect(self._path)
            self._sock = s
        except OSError:
            self._sock = None

    def send(self, command) -> None:
        self._ensure()
        if self._sock is None:
            return
        try:
            self._sock.sendall(encode(command).encode("utf-8"))
        except OSError:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None  # reset → next send reconnects
```

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(overlay): fire-and-forget socket client (silent-fail, auto-reconnect)"`

---

## Task 5: Launcher (socket path + spawn-if-absent)

**Files:** Create `src/daimon/overlay/launcher.py`, `tests/test_overlay_launcher.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_overlay_launcher.py
from daimon.overlay import launcher


def test_socket_path_is_stable_and_in_tmp(monkeypatch):
    monkeypatch.setenv("TMPDIR", "/tmp/")
    assert launcher.socket_path().endswith("daimon-overlay.sock")


def test_ensure_running_skips_spawn_when_socket_live(monkeypatch):
    spawned = []
    monkeypatch.setattr(launcher, "_socket_alive", lambda p: True)
    monkeypatch.setattr(launcher, "_spawn", lambda: spawned.append(True))
    launcher.ensure_running()
    assert spawned == []


def test_ensure_running_spawns_when_socket_dead(monkeypatch):
    spawned = []
    monkeypatch.setattr(launcher, "_socket_alive", lambda p: False)
    monkeypatch.setattr(launcher, "_spawn", lambda: spawned.append(True))
    launcher.ensure_running()
    assert spawned == [True]
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `src/daimon/overlay/launcher.py`:
```python
"""Locate / auto-spawn the long-lived overlay helper process."""

from __future__ import annotations

import os
import socket
import subprocess
import sys


def socket_path() -> str:
    return os.path.join(os.environ.get("TMPDIR", "/tmp"), "daimon-overlay.sock")


def _socket_alive(path: str) -> bool:
    if not os.path.exists(path):
        return False
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(0.05)
        s.connect(path)
        s.close()
        return True
    except OSError:
        return False


def _spawn() -> None:
    # Detached overlay process; it owns the AppKit run loop and the socket.
    subprocess.Popen(
        [sys.executable, "-m", "daimon.overlay.app"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def ensure_running() -> None:
    if not _socket_alive(socket_path()):
        _spawn()
```

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(overlay): launcher (socket path + spawn-if-absent)"`

---

## Task 6: Organ lifecycle calls the presenter

**Files:** Modify `src/daimon/motor/organ.py`, Test `tests/test_organ_presenter.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_organ_presenter.py
from daimon.config import ExclusionConfig
from daimon.exclusions import ExclusionFilter
from daimon.motor.actuator import FakeActuator
from daimon.motor.audit import AppendOnlyLedger
from daimon.motor.gate import FakeGate
from daimon.motor.guard import PolicyGuard
from daimon.motor.organ import MotorOrgan
from daimon.motor.probe import FakeProber
from daimon.overlay.presenter import RecordingPresenter
from daimon.motor.types import Declaration, Level, MotorAction, Target


def _organ(tmp_path, ceiling, observed, gate_answer=False, presenter=None):
    guard = PolicyGuard(ExclusionFilter(ExclusionConfig()), ceiling_provider=lambda: ceiling)
    return MotorOrgan(guard=guard, gate=FakeGate(answer=gate_answer), actuator=FakeActuator(),
                      session_log=AppendOnlyLedger(tmp_path / "s.jsonl"), clock=lambda: "T",
                      prober=FakeProber(target=observed), presenter=presenter)


def _act():
    return MotorAction(name="click", level=Level.INPUT, target=Target(role="AXButton", label="x"),
                       declaration=Declaration(reversible=True, intent="i"), params={"x": 1, "y": 1})


def test_allowed_action_presents_intent_then_executed(tmp_path):
    rp = RecordingPresenter()
    organ = _organ(tmp_path, Level.INPUT, Target(role="AXButton", label="Cancel", observed=True), presenter=rp)
    organ.act(_act())
    kinds = [c[0] for c in rp.calls]
    assert kinds[0] == "intent" and "executed" in kinds


def test_gated_denied_presents_gate_then_refused(tmp_path):
    rp = RecordingPresenter()
    organ = _organ(tmp_path, Level.VALIDATION, Target(role="AXButton", label="Send", observed=True),
                   gate_answer=False, presenter=rp)
    organ.act(_act())
    kinds = [c[0] for c in rp.calls]
    assert "gate" in kinds and "refused" in kinds


def test_presenter_receives_observed_target(tmp_path):
    rp = RecordingPresenter()
    observed = Target(role="AXButton", label="Send", observed=True)
    organ = _organ(tmp_path, Level.INPUT, observed, presenter=rp)
    organ.act(_act())  # action claims label "x"; presenter must see observed "Send"
    intent_action = next(a for k, a in rp.calls if k == "intent")
    assert intent_action.target.label == "Send"


def test_no_presenter_defaults_to_null(tmp_path):
    organ = _organ(tmp_path, Level.INPUT, Target(role="AXButton", label="Cancel", observed=True))
    assert organ.act(_act())["status"] == "done"  # works with default NullPresenter
```

- [ ] **Step 2: Run, expect FAIL** (MotorOrgan has no `presenter`).

- [ ] **Step 3: Implement** — modify `organ.py`:
(a) `__init__` gains `presenter=None`; store `self._presenter = presenter or NullPresenter()` (import `from ..overlay.presenter import NullPresenter`).
(b) In `act`, after the re-probe + `decision = self._guard.evaluate(action)`:
```python
        self._present("present_intent", action, decision)
        if decision.verdict == Verdict.REFUSE:
            self._present("present_refused", action, decision.reason)
            return {"status": "refused", "reason": decision.reason}
        if decision.verdict == Verdict.GATE:
            self._present("present_gate", action)
            if not self._gate.confirm(action):
                self._record(action, "denied", {"reason": "human denied"})
                self._present("present_refused", action, "human denied")
                return {"status": "refused", "reason": "human denied"}
            must_log = True
        else:
            must_log = decision.must_log
        if must_log and not self._record(action, "authorized", {"reason": decision.reason}):
            self._present("present_refused", action, "no-log=no-act")
            return {"status": "refused", "reason": "no-log=no-act (audit write failed)"}
        result = self._actuator.execute(action)
        self._record(action, "executed", {"result": result})
        self._present("present_executed", action, result)
        return {"status": "done", "result": result}
```
And a robust helper:
```python
    def _present(self, method: str, *args) -> None:
        try:
            getattr(self._presenter, method)(*args)
        except Exception:
            pass  # presentation never affects the action
```
Keep the existing divergence-log and structure; just thread the presenter calls in. (Note: `present_intent` is called for all verdicts so the overlay shows what was attempted; for REFUSE it is followed by `present_refused`.)

- [ ] **Step 4: Run, expect PASS.** Full suite — existing `MotorOrgan(...)` constructions keep working (presenter defaults to None → NullPresenter); verify no regressions.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(motor): organ drives a Presenter across the action lifecycle"`

---

## Task 7: OverlayConfig

**Files:** Modify `src/daimon/config.py`, Create `config/overlay.example.yaml`, Test `tests/test_overlay_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_overlay_config.py
from daimon.config import load_overlay_config


def test_overlay_defaults(tmp_path):
    cfg = load_overlay_config(tmp_path / "missing.yaml")
    assert cfg.enabled in (True, False)
    assert 0.0 < cfg.opacity <= 1.0
    assert cfg.anti_feedback is True


def test_overlay_loads(tmp_path):
    p = tmp_path / "overlay.yaml"
    p.write_text("overlay:\n  enabled: true\n  opacity: 0.8\n  anti_feedback: false\n", encoding="utf-8")
    cfg = load_overlay_config(p)
    assert cfg.enabled is True and cfg.opacity == 0.8 and cfg.anti_feedback is False
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — append to `config.py` (reuses `os`, `Path`, `yaml`, `dataclass`, `_REPO_ROOT`):
```python
# --- overlay config -------------------------------------------------------
_OVERLAY_DEFAULT = _REPO_ROOT / "config" / "overlay.yaml"
_OVERLAY_EXAMPLE = _REPO_ROOT / "config" / "overlay.example.yaml"


@dataclass(frozen=True)
class OverlayConfig:
    enabled: bool = False
    opacity: float = 0.95
    anti_feedback: bool = True   # exclude the overlay from screen capture


def _overlay_path() -> Path:
    env = os.environ.get("DAIMON_OVERLAY_CONFIG")
    if env:
        return Path(env).expanduser()
    return _OVERLAY_DEFAULT if _OVERLAY_DEFAULT.exists() else _OVERLAY_EXAMPLE


def load_overlay_config(path: Path | None = None) -> OverlayConfig:
    path = path or _overlay_path()
    if not path.exists():
        return OverlayConfig()
    raw = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("overlay", {}) or {}
    return OverlayConfig(
        enabled=bool(raw.get("enabled", False)),
        opacity=float(raw.get("opacity", 0.95)),
        anti_feedback=bool(raw.get("anti_feedback", True)),
    )
```
`config/overlay.example.yaml`:
```yaml
# Daimon overlay ("the face") — premium on-screen presentation of what the
# agent looks at and does. Copy to config/overlay.yaml to enable.
overlay:
  enabled: false        # set true to show the overlay
  opacity: 0.95
  anti_feedback: true   # keep the overlay invisible to Vue screen capture
```
Add `config/overlay.yaml` to `.gitignore`.

- [ ] **Step 4: Run, expect PASS.** Full suite green.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(overlay): OverlayConfig (enabled/opacity/anti_feedback)"`

---

## Task 8: Overlay GUI process (macOS, smoke-only)

**Files:** Create `src/daimon/overlay/app/__init__.py`, `app/window.py`, `app/scene.py`, `app/server.py`, `app/__main__.py`

No unit tests (AppKit). Acceptance = imports are syntactically valid on import-skip and the smoke script (Task 9) runs on a real Mac.

- [ ] **Step 1:** Create `src/daimon/overlay/app/__init__.py`:
```python
"""The overlay helper process: NSApplication run loop + socket server + drawing.
macOS-only; imported and run as `python -m daimon.overlay.app`."""
```

- [ ] **Step 2:** Create `src/daimon/overlay/app/window.py`:
```python
"""Transparent, click-through, capture-invisible overlay window."""

from __future__ import annotations


def make_overlay_window(anti_feedback: bool = True):
    from AppKit import (
        NSWindow, NSScreen, NSColor, NSWindowStyleMaskBorderless,
        NSBackingStoreBuffered, NSWindowCollectionBehaviorCanJoinAllSpaces,
        NSWindowCollectionBehaviorStationary, NSScreenSaverWindowLevel,
        NSWindowSharingNone,
    )
    frame = NSScreen.mainScreen().frame()
    win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        frame, NSWindowStyleMaskBorderless, NSBackingStoreBuffered, False)
    win.setOpaque_(False)
    win.setBackgroundColor_(NSColor.clearColor())
    win.setLevel_(NSScreenSaverWindowLevel)          # above normal windows
    win.setIgnoresMouseEvents_(True)                  # click-through
    win.setCollectionBehavior_(
        NSWindowCollectionBehaviorCanJoinAllSpaces | NSWindowCollectionBehaviorStationary)
    if anti_feedback:
        win.setSharingType_(NSWindowSharingNone)      # invisible to screen capture
    win.contentView().setWantsLayer_(True)
    win.orderFrontRegardless()
    return win
```

- [ ] **Step 3:** Create `src/daimon/overlay/app/scene.py` (CALayer scene; one method per command):
```python
"""Core-Animation scene: applies overlay protocol commands to CALayers."""

from __future__ import annotations

from ..theme import style_for


class Scene:
    def __init__(self, layer):
        self._root = layer
        self._nodes = {}   # keyed transient layers

    def _nscolor(self, rgba, opacity=1.0):
        from AppKit import NSColor
        r, g, b, a = rgba
        return NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, a * opacity).CGColor()

    def apply(self, cmd) -> None:
        getattr(self, f"_do_{cmd.cmd}", self._noop)(cmd)

    def _noop(self, cmd): pass

    def _do_highlight(self, cmd):
        import Quartz
        st = style_for(cmd.style)
        h = self._nodes.get("highlight") or Quartz.CAShapeLayer.layer()
        h.setFrame_(((cmd.x, cmd.y), (cmd.w, cmd.h)))
        h.setCornerRadius_(st["radius"])
        h.setBorderWidth_(2.5)
        h.setBorderColor_(self._nscolor(st["rgba"]))
        h.setBackgroundColor_(self._nscolor(st["rgba"], 0.08))
        if "highlight" not in self._nodes:
            self._root.addSublayer_(h); self._nodes["highlight"] = h
        if st["pulse"]:
            self._pulse(h, st["duration"])

    def _do_spotlight(self, cmd):
        pass  # vignette mask — premium; drawn as a dimmed full-screen layer with a clear hole

    def _do_cursor(self, cmd):
        import Quartz
        c = self._nodes.get("cursor") or Quartz.CALayer.layer()
        c.setFrame_(((cmd.x - 12, cmd.y - 12), (24, 24)))
        c.setCornerRadius_(12)
        c.setBackgroundColor_(self._nscolor((0.25, 0.55, 0.95, 1.0), 0.25))
        if "cursor" not in self._nodes:
            self._root.addSublayer_(c); self._nodes["cursor"] = c

    def _do_ripple(self, cmd):
        import Quartz
        r = Quartz.CALayer.layer()
        r.setFrame_(((cmd.x - 4, cmd.y - 4), (8, 8)))
        r.setCornerRadius_(4)
        r.setBackgroundColor_(self._nscolor((0.25, 0.55, 0.95, 1.0)))
        self._root.addSublayer_(r)
        self._ripple(r)

    def _do_banner(self, cmd):
        import Quartz
        from ..theme import style_for as sf
        t = self._nodes.get("banner") or Quartz.CATextLayer.layer()
        t.setString_(cmd.text)
        t.setFontSize_(13)
        t.setForegroundColor_(self._nscolor((1, 1, 1, 1)))
        t.setBackgroundColor_(self._nscolor(sf(cmd.level)["rgba"], 0.85))
        t.setCornerRadius_(8)
        t.setAlignmentMode_("center")
        t.setFrame_(((40, 40), (480, 28)))
        if "banner" not in self._nodes:
            self._root.addSublayer_(t); self._nodes["banner"] = t

    def _do_clear(self, cmd):
        for layer in list(self._nodes.values()):
            layer.removeFromSuperlayer()
        self._nodes.clear()

    def _pulse(self, layer, duration):
        import Quartz
        a = Quartz.CABasicAnimation.animationWithKeyPath_("opacity")
        a.setFromValue_(1.0); a.setToValue_(0.45)
        a.setDuration_(duration); a.setAutoreverses_(True); a.setRepeatCount_(1e9)
        layer.addAnimation_forKey_(a, "pulse")

    def _ripple(self, layer):
        import Quartz
        grow = Quartz.CABasicAnimation.animationWithKeyPath_("transform.scale")
        grow.setFromValue_(1.0); grow.setToValue_(6.0); grow.setDuration_(0.5)
        fade = Quartz.CABasicAnimation.animationWithKeyPath_("opacity")
        fade.setFromValue_(0.8); fade.setToValue_(0.0); fade.setDuration_(0.5)
        layer.addAnimation_forKey_(grow, "grow")
        layer.addAnimation_forKey_(fade, "fade")
```
(Note: macOS layer Y-origin is bottom-left; coordinate flipping vs global screen points is handled in `server.py` when applying — document and convert there. Keep `scene` in window-local coords.)

- [ ] **Step 4:** Create `src/daimon/overlay/app/server.py` (socket read loop feeding the scene on the main thread via performSelectorOnMainThread or a CFRunLoop source; simplest robust approach: a background thread reads lines and dispatches each command to the main thread):
```python
"""Socket server for the overlay process: reads command lines, applies them to
the Scene on the AppKit main thread."""

from __future__ import annotations

import os
import socket
import threading

from ..launcher import socket_path
from ..protocol import decode


class OverlayServer:
    def __init__(self, scene, flip_height: float):
        self._scene = scene
        self._flip = flip_height

    def start(self) -> None:
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        path = socket_path()
        try:
            os.unlink(path)
        except OSError:
            pass
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(path); srv.listen(1)
        while True:
            conn, _ = srv.accept()
            buf = b""
            with conn:
                while True:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        if line.strip():
                            self._dispatch(line.decode("utf-8"))

    def _dispatch(self, line: str) -> None:
        try:
            cmd = decode(line)
        except ValueError:
            return
        # flip Y from global top-left to window bottom-left, then apply on main thread
        from AppKit import NSApp
        from libdispatch import dispatch_async, dispatch_get_main_queue  # pyobjc dispatch
        def _apply():
            self._scene.apply(self._flip_cmd(cmd))
        try:
            dispatch_async(dispatch_get_main_queue(), _apply)
        except Exception:
            self._scene.apply(self._flip_cmd(cmd))

    def _flip_cmd(self, cmd):
        from dataclasses import replace
        if hasattr(cmd, "y"):
            return replace(cmd, y=int(self._flip - cmd.y))
        return cmd
```
(If `libdispatch` import is unavailable, fall back to `PyObjCTools.AppHelper.callAfter`. The implementer should use whichever pyobjc dispatch primitive is present; document the choice.)

- [ ] **Step 5:** Create `src/daimon/overlay/app/__main__.py`:
```python
"""Overlay process entry: build the window, scene, socket server, run AppKit."""

from __future__ import annotations


def main() -> None:
    from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
    from PyObjCTools import AppHelper
    from ...config import load_overlay_config
    from .window import make_overlay_window
    from .scene import Scene
    from .server import OverlayServer

    cfg = load_overlay_config()
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)  # no Dock icon
    win = make_overlay_window(anti_feedback=cfg.anti_feedback)
    win.contentView().layer().setOpacity_(cfg.opacity)
    scene = Scene(win.contentView().layer())
    OverlayServer(scene, flip_height=win.frame().size.height).start()
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
```

- [ ] **Step 6:** Verify import safety on the host: `PYTHONPATH=src python -c "import daimon.overlay.app.window, daimon.overlay.app.scene, daimon.overlay.app.server"` (macOS imports are deferred inside functions, so module import must NOT require AppKit at import time — confirm no top-level AppKit imports). Fix any top-level macOS import that breaks bare import.

- [ ] **Step 7: Commit** — `git add -A && git commit -m "feat(overlay): macOS GUI process (window/scene/server/entry, CALayer animations)"`

---

## Task 9: Server wiring + overlay tools + smoke

**Files:** Modify `src/daimon/server.py`, `src/daimon/motor/factory.py`, Create `scripts/smoke_overlay.py`, Test `tests/test_overlay_tools.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_overlay_tools.py
import asyncio
from daimon.server import build_server


def test_overlay_tools_registered():
    names = {t.name for t in asyncio.run(build_server().list_tools())}
    assert {"overlay_highlight", "overlay_spotlight", "overlay_cursor",
            "overlay_banner", "overlay_clear"} <= names
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement**
(a) `factory.py` `build_organ`: build the presenter from config — if `load_overlay_config().enabled`, `launcher.ensure_running()` then `OverlayPresenter(OverlayClient(launcher.socket_path()), exclusions)`, else `NullPresenter()`. Pass `presenter=...` to `MotorOrgan`. Reuse the exclusions already built.
(b) `server.py`: register five `overlay_*` tools that send protocol commands through a shared `OverlayClient` (created once, gated on config.enabled; when disabled the client send is a silent no-op because the socket won't connect — still safe to register). Each tool builds the matching protocol command and calls `client.send(...)`, returning `{"ok": True}`.
```python
    @mcp.tool(name="overlay_highlight", description="Outline a screen rect with an optional label.")
    def overlay_highlight(x: int, y: int, width: int, height: int, label: str = "") -> dict:
        client.send(Highlight(x=x, y=y, w=width, h=height, label=label)); return {"ok": True}
    # ... spotlight / cursor / banner / clear similarly
```
(c) `scripts/smoke_overlay.py`: `launcher.ensure_running()`, wait briefly, then send a demo sequence (highlight → banner → ripple → gate-style highlight → clear) via OverlayClient, printing each step.

- [ ] **Step 4: Run** — `PYTHONPATH=src python -m pytest tests/test_overlay_tools.py -v` + full suite. Print the tool list; confirm the 5 overlay tools + all prior tools.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(overlay): wire presenter from config; register overlay_* tools; smoke script"`

---

## Task 10: Full suite + docs

- [ ] **Step 1:** `PYTHONPATH=src python -m pytest -q` — all pass.
- [ ] **Step 2:** README — add a "## The face (overlay)" section: the third organ; premium click-through, capture-invisible (anti-feedback) overlay; auto-shows what the agent targets/does and emphasises the gate target; driven by `overlay_*` tools; enable via `config/overlay.yaml`; runs as a helper process `python -m daimon.overlay.app`; never on an action's critical path.
- [ ] **Step 3:** Commit — `git add README.md && git commit -m "docs: the face (overlay) organ"`

---

## Self-review

- **Spec coverage:** §3 visual elements → protocol (T1) + scene (T8); §4 security (click-through/sharingNone/secret-safe/degrade) → window (T8) + presenter redaction (T3) + client silent-fail (T4) + organ `_present` swallow (T6); §5 motor integration → organ (T6) + factory (T9); §5 MCP tools → server (T9); §6 module layout → all; §7 IPC → protocol (T1) + client (T4) + server (T8); §8 tests → pure unit (T1-T7) + smoke (T9). ✓
- **Placeholders:** spotlight `_do_spotlight` is a documented minimal stub (premium vignette can deepen later) — acceptable for v1; not a TBD requirement. All other code complete.
- **Type consistency:** protocol command classes used identically across presenter (T3), client (T4), server (T8/T9); `Presenter` protocol methods match organ calls (T6) and presenter impls (T3); `OverlayPresenter(sink, exclusions)` signature consistent (T3/T9). ✓
- **Invariant check:** overlay never on critical path — `_present` swallows, client silent-fails, presenter `_send` swallows (three layers). Secret-safe — presenter `_label` redacts via `is_target_secret`. Anti-feedback — `setSharingType_(NSWindowSharingNone)`. ✓
