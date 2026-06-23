# Pacte — Cooperative App Channel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Daimon a generic cooperative channel (`Pacte` organ: `pacte_describe` / `pacte_probe` / `pacte_act`) so an autonomous agent can drive and observe in-app manipulation an OS-level organ cannot see, while Daimon stays app-agnostic and the security contract (ceiling + redaction + ledger) is enforced unchanged.

**Architecture:** A new `src/daimon/pacte/` organ speaks JSON-RPC 2.0 over loopback TCP to a cooperating app's `--dev` endpoint, discovered via a token-authenticated file. `pacte_act` reuses the existing `MotorOrgan` by plugging in a `CooperativeActuator` (executes via the channel) and a `CooperativeGate` (durable per-session consent instead of a per-action dialog); `pacte_probe` runs through the existing `ExclusionFilter.redact_nodes`. No Qt enters Daimon.

**Tech Stack:** Python 3, FastMCP (`mcp.server.fastmcp`), stdlib `socket`/`json`, existing `daimon.motor` (`MotorOrgan`, `PolicyGuard`, `AppendOnlyLedger`, `Level`, `MotorAction`), existing `daimon.exclusions.ExclusionFilter`. Tests: `/Users/Ben/.hfenv/bin/pytest`.

## Global Constraints

- **No Qt / PyQt / PySide dependency may be added to Daimon.** The organ speaks only the JSON-RPC protocol.
- **Loopback only.** The client connects to `127.0.0.1` and presents the discovery-file token on every request.
- **Discovery file**: `~/.daimon/cooperative/<app>-<pid>.json` = `{port:int, token:str, pid:int, app:str, protocol_version:str}`. Protocol version this plan implements: `"1.0"`.
- **Hands ladder (verbatim from `motor/types.py`)**: `READ=0, NONDESTRUCTIVE=1, INPUT=2, VALIDATION=3, AUTONOMOUS=4`.
- **Security**: `pacte_act` passes through a `PolicyGuard` (level ≤ ceiling, exclusions, reversibility) and the `MotorOrgan.act` chokepoint (no-log = no-act). Acts are only authorized inside an open cooperative session, capped at session ceiling (default `VALIDATION`, never `AUTONOMOUS`). `pacte_probe` output is redacted via `ExclusionFilter.redact_nodes`.
- **Tools register always**; with no discovery file present, `pacte_describe` returns a clear "no cooperative app found" payload and `pacte_probe`/`pacte_act` return a refusal — never crash.
- Follow existing module style: module docstring, `from __future__ import annotations`, small focused files.

---

### Task 1: Protocol envelope + message schema

**Files:**
- Create: `src/daimon/pacte/__init__.py` (empty package marker)
- Create: `src/daimon/pacte/protocol.py`
- Test: `tests/test_pacte_protocol.py`

**Interfaces:**
- Produces:
  - `PROTOCOL_VERSION: str = "1.0"`
  - `def build_request(method: str, params: dict, token: str, rid: int) -> dict` — a JSON-RPC 2.0 request dict `{"jsonrpc":"2.0","id":rid,"method":method,"params":{**params,"token":token}}`.
  - `def parse_response(raw: dict, rid: int) -> dict` — returns `raw["result"]` when `id==rid` and no `error`; raises `ProtocolError` on id mismatch, on a JSON-RPC `error` object, or on a missing `result`.
  - `class ProtocolError(Exception)`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pacte_protocol.py
import pytest
from daimon.pacte.protocol import build_request, parse_response, ProtocolError, PROTOCOL_VERSION


def test_build_request_is_jsonrpc_2_and_carries_token():
    req = build_request("probe", {"fields": ["dirty"]}, token="abc", rid=7)
    assert req == {
        "jsonrpc": "2.0", "id": 7, "method": "probe",
        "params": {"fields": ["dirty"], "token": "abc"},
    }


def test_parse_response_returns_result_on_matching_id():
    assert parse_response({"jsonrpc": "2.0", "id": 7, "result": {"dirty": True}}, rid=7) == {"dirty": True}


def test_parse_response_raises_on_id_mismatch():
    with pytest.raises(ProtocolError):
        parse_response({"jsonrpc": "2.0", "id": 9, "result": {}}, rid=7)


def test_parse_response_raises_on_error_object():
    with pytest.raises(ProtocolError):
        parse_response({"jsonrpc": "2.0", "id": 7, "error": {"code": -32000, "message": "bad verb"}}, rid=7)


def test_protocol_version_is_one():
    assert PROTOCOL_VERSION == "1.0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_pacte_protocol.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'daimon.pacte'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/daimon/pacte/__init__.py
```

```python
# src/daimon/pacte/protocol.py
"""JSON-RPC 2.0 envelope + schema for the cooperative channel. Pure — no I/O."""

from __future__ import annotations

PROTOCOL_VERSION = "1.0"


class ProtocolError(Exception):
    """A malformed, mismatched, or error JSON-RPC response."""


def build_request(method: str, params: dict, token: str, rid: int) -> dict:
    """Build a JSON-RPC 2.0 request with the auth token folded into params."""
    return {"jsonrpc": "2.0", "id": rid, "method": method, "params": {**params, "token": token}}


def parse_response(raw: dict, rid: int) -> dict:
    """Return the result for `rid`; raise ProtocolError on mismatch/error/missing result."""
    if raw.get("id") != rid:
        raise ProtocolError(f"response id {raw.get('id')!r} != request id {rid!r}")
    if "error" in raw:
        err = raw["error"]
        raise ProtocolError(f"endpoint error {err.get('code')}: {err.get('message')}")
    if "result" not in raw:
        raise ProtocolError("response has neither result nor error")
    return raw["result"]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_pacte_protocol.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/daimon/pacte/__init__.py src/daimon/pacte/protocol.py tests/test_pacte_protocol.py
git commit -m "feat(pacte): JSON-RPC protocol envelope for the cooperative channel"
```

---

### Task 2: Discovery + token handshake

**Files:**
- Create: `src/daimon/pacte/discovery.py`
- Test: `tests/test_pacte_discovery.py`

**Interfaces:**
- Consumes: `PROTOCOL_VERSION` from `protocol.py`.
- Produces:
  - `@dataclass(frozen=True) class Endpoint: port:int; token:str; pid:int; app:str; protocol_version:str`
  - `def discover(cooperative_dir: Path) -> Endpoint | None` — newest valid discovery file in the dir → `Endpoint`; `None` if the dir is absent/empty or no file is valid. A file is valid when it parses as JSON, has all five keys, and `protocol_version == PROTOCOL_VERSION`. Newest = highest mtime.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pacte_discovery.py
import json
from pathlib import Path
from daimon.pacte.discovery import discover, Endpoint


def _write(dirp: Path, name: str, **over):
    rec = {"port": 5000, "token": "t", "pid": 1, "app": "delta", "protocol_version": "1.0"}
    rec.update(over)
    dirp.mkdir(parents=True, exist_ok=True)
    (dirp / name).write_text(json.dumps(rec), encoding="utf-8")
    return dirp / name


def test_discover_none_when_dir_absent(tmp_path):
    assert discover(tmp_path / "nope") is None


def test_discover_returns_endpoint(tmp_path):
    _write(tmp_path, "delta-1.json", port=5050, token="abc", pid=42)
    ep = discover(tmp_path)
    assert ep == Endpoint(port=5050, token="abc", pid=42, app="delta", protocol_version="1.0")


def test_discover_skips_wrong_protocol_version(tmp_path):
    _write(tmp_path, "delta-1.json", protocol_version="0.9")
    assert discover(tmp_path) is None


def test_discover_picks_newest(tmp_path):
    import os, time
    a = _write(tmp_path, "delta-1.json", port=1)
    b = _write(tmp_path, "delta-2.json", port=2)
    os.utime(a, (1, 1))
    os.utime(b, (2, 2))
    assert discover(tmp_path).port == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_pacte_discovery.py -v`
Expected: FAIL with `ModuleNotFoundError`/`ImportError` for `daimon.pacte.discovery`

- [ ] **Step 3: Write minimal implementation**

```python
# src/daimon/pacte/discovery.py
"""Find a cooperating app's loopback endpoint via its discovery file. FS + validation only."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .protocol import PROTOCOL_VERSION

_KEYS = ("port", "token", "pid", "app", "protocol_version")


@dataclass(frozen=True)
class Endpoint:
    """A discovered cooperative endpoint: where to connect and the token to present."""

    port: int
    token: str
    pid: int
    app: str
    protocol_version: str


def _load(path: Path) -> Endpoint | None:
    try:
        rec = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not all(k in rec for k in _KEYS) or rec["protocol_version"] != PROTOCOL_VERSION:
        return None
    return Endpoint(port=int(rec["port"]), token=str(rec["token"]), pid=int(rec["pid"]),
                    app=str(rec["app"]), protocol_version=str(rec["protocol_version"]))


def discover(cooperative_dir: Path) -> Endpoint | None:
    """Newest valid discovery file in `cooperative_dir` → Endpoint, else None."""
    cooperative_dir = Path(cooperative_dir)
    if not cooperative_dir.is_dir():
        return None
    files = sorted(cooperative_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    for f in files:
        ep = _load(f)
        if ep is not None:
            return ep
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_pacte_discovery.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/daimon/pacte/discovery.py tests/test_pacte_discovery.py
git commit -m "feat(pacte): endpoint discovery + protocol-version gate"
```

---

### Task 3: Fake endpoint test double + socket client

**Files:**
- Create: `tests/fakes/__init__.py`
- Create: `tests/fakes/cooperative_endpoint.py` (in-process JSON-RPC TCP server, no Qt)
- Create: `src/daimon/pacte/client.py`
- Test: `tests/test_pacte_client.py`

**Interfaces:**
- Consumes: `build_request` / `parse_response` / `ProtocolError` from `protocol.py`; `Endpoint` from `discovery.py`.
- Produces:
  - `tests/fakes/cooperative_endpoint.py`: `class FakeCooperativeEndpoint` — `start() -> Endpoint` (binds loopback, returns its `Endpoint` with the real port + a known token), `stop()`, `requests: list[dict]` (every request seen), and a settable `handlers: dict[str, callable]` mapping method → `params -> result`. Rejects requests whose `token` mismatches with a JSON-RPC error.
  - `src/daimon/pacte/client.py`: `class CooperativeClient` — `__init__(endpoint: Endpoint)`, `def call(self, method: str, params: dict, timeout: float = 5.0) -> dict` (sends one newline-delimited JSON request, reads one response line, returns `parse_response(...)`). Auto-increments request ids. Raises `ProtocolError` on a transport/JSON failure.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pacte_client.py
import pytest
from daimon.pacte.client import CooperativeClient
from daimon.pacte.protocol import ProtocolError
from tests.fakes.cooperative_endpoint import FakeCooperativeEndpoint


def test_client_round_trips_a_method():
    fake = FakeCooperativeEndpoint(token="secret")
    fake.handlers["probe"] = lambda params: {"dirty": True, "echo": params.get("fields")}
    ep = fake.start()
    try:
        client = CooperativeClient(ep)
        result = client.call("probe", {"fields": ["dirty"]})
        assert result == {"dirty": True, "echo": ["dirty"]}
        assert fake.requests[-1]["params"]["token"] == "secret"
    finally:
        fake.stop()


def test_client_raises_on_bad_token():
    fake = FakeCooperativeEndpoint(token="secret")
    ep = fake.start()
    # tamper: present the wrong token
    from daimon.pacte.discovery import Endpoint
    bad = Endpoint(port=ep.port, token="wrong", pid=ep.pid, app=ep.app, protocol_version=ep.protocol_version)
    try:
        with pytest.raises(ProtocolError):
            CooperativeClient(bad).call("probe", {})
    finally:
        fake.stop()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_pacte_client.py -v`
Expected: FAIL with import error for `tests.fakes.cooperative_endpoint` / `daimon.pacte.client`

- [ ] **Step 3: Write the fake endpoint and the client**

```python
# tests/fakes/__init__.py
```

```python
# tests/fakes/cooperative_endpoint.py
"""In-process JSON-RPC TCP test double for the cooperative channel. No Qt."""

from __future__ import annotations

import json
import socket
import threading

from daimon.pacte.discovery import Endpoint
from daimon.pacte.protocol import PROTOCOL_VERSION


class FakeCooperativeEndpoint:
    def __init__(self, token: str = "secret", app: str = "fake"):
        self.token = token
        self.app = app
        self.requests: list[dict] = []
        self.handlers: dict = {}
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = False

    def start(self) -> Endpoint:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(8)
        port = self._sock.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        return Endpoint(port=port, token=self.token, pid=0, app=self.app,
                        protocol_version=PROTOCOL_VERSION)

    def _serve(self):
        while not self._stop:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            with conn:
                data = conn.makefile("r")
                line = data.readline()
                if not line:
                    continue
                req = json.loads(line)
                self.requests.append(req)
                rid = req.get("id")
                params = req.get("params", {})
                if params.get("token") != self.token:
                    resp = {"jsonrpc": "2.0", "id": rid,
                            "error": {"code": -32001, "message": "bad token"}}
                else:
                    handler = self.handlers.get(req.get("method"), lambda p: {})
                    resp = {"jsonrpc": "2.0", "id": rid, "result": handler(params)}
                conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

    def stop(self):
        self._stop = True
        if self._sock is not None:
            self._sock.close()
```

```python
# src/daimon/pacte/client.py
"""Loopback TCP transport for the cooperative channel. One request → one response line."""

from __future__ import annotations

import json
import socket

from .discovery import Endpoint
from .protocol import ProtocolError, build_request, parse_response


class CooperativeClient:
    """Sends newline-delimited JSON-RPC requests to a discovered loopback endpoint."""

    def __init__(self, endpoint: Endpoint) -> None:
        self._ep = endpoint
        self._rid = 0

    def call(self, method: str, params: dict, timeout: float = 5.0) -> dict:
        """Round-trip one JSON-RPC call; raise ProtocolError on any transport/JSON failure."""
        self._rid += 1
        rid = self._rid
        req = build_request(method, params, token=self._ep.token, rid=rid)
        try:
            with socket.create_connection(("127.0.0.1", self._ep.port), timeout=timeout) as s:
                s.settimeout(timeout)
                s.sendall((json.dumps(req) + "\n").encode("utf-8"))
                raw = s.makefile("r").readline()
        except OSError as e:
            raise ProtocolError(f"transport failure: {e}") from e
        if not raw:
            raise ProtocolError("empty response")
        try:
            decoded = json.loads(raw)
        except ValueError as e:
            raise ProtocolError(f"bad JSON response: {e}") from e
        return parse_response(decoded, rid)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_pacte_client.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add tests/fakes/__init__.py tests/fakes/cooperative_endpoint.py src/daimon/pacte/client.py tests/test_pacte_client.py
git commit -m "feat(pacte): loopback TCP client + in-process fake endpoint test double"
```

---

### Task 4: Cooperative session + durable-consent gate

**Files:**
- Create: `src/daimon/pacte/session.py`
- Create: `src/daimon/pacte/gate.py`
- Test: `tests/test_pacte_session.py`

**Interfaces:**
- Consumes: `AppendOnlyLedger` from `daimon.motor.audit`; `Level` from `daimon.motor.types`; `MotorAction` from `daimon.motor.types`.
- Produces:
  - `session.py`:
    - `DEFAULT_SESSION_CEILING: Level = Level.VALIDATION`
    - `class CooperativeSession`: `__init__(ledger: AppendOnlyLedger, clock: Callable[[], str], ceiling: Level = DEFAULT_SESSION_CEILING)`. Methods: `open(app: str, pid: int) -> None` (records one ledger entry `{"event":"cooperative_open","app","pid","ceiling":<name>}`, sets active), `close() -> None` (records `{"event":"cooperative_close"}`, clears active), `active() -> bool`, `ceiling() -> Level` (the session ceiling while active, else `Level.READ`). `ceiling` passed above `VALIDATION` is clamped to `VALIDATION` (never autonomous via this channel).
  - `gate.py`:
    - `class CooperativeGate`: `__init__(session: CooperativeSession)`. `confirm(action: MotorAction) -> bool` — returns `True` iff `session.active()` and `action.level <= session.ceiling()`; else `False`. (Satisfies `HumanGate`'s `confirm` contract used by `MotorOrgan`.)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pacte_session.py
from daimon.motor.audit import AppendOnlyLedger
from daimon.motor.types import Level, MotorAction, Target, Declaration
from daimon.pacte.session import CooperativeSession, DEFAULT_SESSION_CEILING
from daimon.pacte.gate import CooperativeGate


def _ledger(tmp_path):
    return AppendOnlyLedger(tmp_path / "c.jsonl")


def _action(level):
    return MotorAction(name="drag", level=level, target=Target(observed=True),
                       declaration=Declaration(reversible=True, intent="t"))


def test_closed_session_has_read_ceiling(tmp_path):
    s = CooperativeSession(_ledger(tmp_path), clock=lambda: "ts")
    assert s.active() is False
    assert s.ceiling() == Level.READ


def test_open_records_one_entry_and_raises_ceiling(tmp_path):
    led = _ledger(tmp_path)
    s = CooperativeSession(led, clock=lambda: "ts")
    s.open(app="delta", pid=42)
    assert s.active() is True
    assert s.ceiling() == DEFAULT_SESSION_CEILING
    recs = led._records()
    assert recs[-1]["event"] == "cooperative_open" and recs[-1]["app"] == "delta"


def test_ceiling_clamped_below_autonomous(tmp_path):
    s = CooperativeSession(_ledger(tmp_path), clock=lambda: "ts", ceiling=Level.AUTONOMOUS)
    s.open(app="delta", pid=1)
    assert s.ceiling() == Level.VALIDATION


def test_gate_confirms_within_ceiling_only_when_open(tmp_path):
    s = CooperativeSession(_ledger(tmp_path), clock=lambda: "ts")
    gate = CooperativeGate(s)
    assert gate.confirm(_action(Level.INPUT)) is False          # not open
    s.open(app="delta", pid=1)
    assert gate.confirm(_action(Level.INPUT)) is True           # within ceiling
    assert gate.confirm(_action(Level.AUTONOMOUS)) is False     # above ceiling
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_pacte_session.py -v`
Expected: FAIL with import error for `daimon.pacte.session`

- [ ] **Step 3: Write minimal implementation**

```python
# src/daimon/pacte/session.py
"""The cooperative test session: durable, ledgered pre-authorization for pacte_act."""

from __future__ import annotations

from typing import Callable

from ..motor.audit import AppendOnlyLedger
from ..motor.types import Level

DEFAULT_SESSION_CEILING = Level.VALIDATION


class CooperativeSession:
    """Active flag + ceiling for a cooperative drive session, recorded immutably."""

    def __init__(self, ledger: AppendOnlyLedger, clock: Callable[[], str],
                 ceiling: Level = DEFAULT_SESSION_CEILING) -> None:
        self._ledger = ledger
        self._clock = clock
        self._ceiling = min(ceiling, Level.VALIDATION)
        self._active = False

    def open(self, app: str, pid: int) -> None:
        """Begin a session: one ledger entry pre-authorizes acts up to the session ceiling."""
        self._ledger.append({"event": "cooperative_open", "ts": self._clock(),
                             "app": app, "pid": pid, "ceiling": self._ceiling.name})
        self._active = True

    def close(self) -> None:
        """End the session; record it. Acts refuse again until the next open()."""
        self._ledger.append({"event": "cooperative_close", "ts": self._clock()})
        self._active = False

    def active(self) -> bool:
        return self._active

    def ceiling(self) -> Level:
        return self._ceiling if self._active else Level.READ
```

```python
# src/daimon/pacte/gate.py
"""The gate MotorOrgan calls for cooperative acts: satisfied by the durable session consent."""

from __future__ import annotations

from ..motor.types import MotorAction
from .session import CooperativeSession


class CooperativeGate:
    """Confirms an act iff a session is open and the act is within the session ceiling."""

    def __init__(self, session: CooperativeSession) -> None:
        self._session = session

    def confirm(self, action: MotorAction) -> bool:
        """No live dialog: the open-session ledger entry is the standing consent."""
        return self._session.active() and action.level <= self._session.ceiling()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_pacte_session.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/daimon/pacte/session.py src/daimon/pacte/gate.py tests/test_pacte_session.py
git commit -m "feat(pacte): durable cooperative session consent + gate"
```

---

### Task 5: Cooperative actuator (channel-backed execution)

**Files:**
- Create: `src/daimon/pacte/actuator.py`
- Test: `tests/test_pacte_actuator.py`

**Interfaces:**
- Consumes: `CooperativeClient` from `client.py`; `MotorAction` from `daimon.motor.types`.
- Produces:
  - `class CooperativeActuator`: `__init__(client: CooperativeClient)`. `def execute(self, action: MotorAction) -> dict` — sends JSON-RPC `act` with `{"verb": action.name, "args": action.params.get("args", {})}` and returns the endpoint's `result`. (Satisfies the `Actuator.execute` contract `MotorOrgan` calls.)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pacte_actuator.py
from daimon.motor.types import MotorAction, Target, Declaration, Level
from daimon.pacte.actuator import CooperativeActuator
from daimon.pacte.client import CooperativeClient
from tests.fakes.cooperative_endpoint import FakeCooperativeEndpoint


def test_actuator_sends_act_verb_and_args():
    fake = FakeCooperativeEndpoint(token="secret")
    fake.handlers["act"] = lambda p: {"ok": True, "verb": p["verb"], "args": p["args"]}
    ep = fake.start()
    try:
        actuator = CooperativeActuator(CooperativeClient(ep))
        action = MotorAction(
            name="drag", level=Level.INPUT, target=Target(observed=True),
            declaration=Declaration(reversible=True, intent="move node"),
            params={"args": {"target": "n1", "to": {"scene_x": 10, "scene_y": 20}}},
        )
        result = actuator.execute(action)
        assert result == {"ok": True, "verb": "drag", "args": {"target": "n1", "to": {"scene_x": 10, "scene_y": 20}}}
    finally:
        fake.stop()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_pacte_actuator.py -v`
Expected: FAIL with import error for `daimon.pacte.actuator`

- [ ] **Step 3: Write minimal implementation**

```python
# src/daimon/pacte/actuator.py
"""Execute an authorized MotorAction by forwarding it over the cooperative channel."""

from __future__ import annotations

from ..motor.types import MotorAction
from .client import CooperativeClient


class CooperativeActuator:
    """The MotorOrgan actuator slot, backed by the JSON-RPC channel instead of the OS."""

    def __init__(self, client: CooperativeClient) -> None:
        self._client = client

    def execute(self, action: MotorAction) -> dict:
        """Forward the verb + args to the endpoint's `act` method; return its result."""
        return self._client.call("act", {"verb": action.name, "args": action.params.get("args", {})})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_pacte_actuator.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add src/daimon/pacte/actuator.py tests/test_pacte_actuator.py
git commit -m "feat(pacte): channel-backed actuator for MotorOrgan"
```

---

### Task 6: Pacte organ — register `describe` / `probe` / `act`

**Files:**
- Create: `src/daimon/pacte/organ.py`
- Test: `tests/test_pacte_organ.py`

**Interfaces:**
- Consumes: `CooperativeClient`, `CooperativeSession`, `CooperativeActuator`, `CooperativeGate`, `discover`, `Endpoint`; `MotorOrgan`, `PolicyGuard`, `MotorAction`, `Target`, `Declaration`, `Level` from `daimon.motor`; `AppendOnlyLedger` from `daimon.motor.audit`; `ExclusionFilter` from `daimon.exclusions`.
- Produces:
  - `class Pacte`: `__init__(exclusions: ExclusionFilter, session: CooperativeSession, motor_organ_factory: Callable[[CooperativeClient], MotorOrgan], discover_fn=discover, cooperative_dir: Path | None = None)`. `def register(self, mcp) -> None` registering three tools:
    - `pacte_describe()` → `{"connected": False, "reason": "..."}` if `discover_fn` returns `None`; else opens a `CooperativeSession`, builds the client + `MotorOrgan`, calls `describe`, returns `{"connected": True, "app", "manifest"}`.
    - `pacte_probe(fields: list[str] | None = None)` → refusal dict if no connected session; else `client.call("probe", {...})`, run the returned `items`/`decorators`/etc. node-bearing lists through `exclusions.redact_nodes`, return redacted payload.
    - `pacte_act(verb: str, args: dict, intent: str, level: int, reversible: bool = True)` → build a `MotorAction(name=verb, level=Level(level), target=Target(observed=True), declaration=Declaration(reversible, intent), params={"args": args})` and return `motor_organ.act(action)`.

  Note: `Target(observed=True)` is intentional — the cooperating endpoint is authoritative for target existence (an invalid `node_id` returns a JSON-RPC error), so the OS-target observation step does not apply on this channel; the guard's ceiling/exclusion/reversibility checks still run.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pacte_organ.py
from pathlib import Path
import pytest

from daimon.config import ExclusionConfig
from daimon.exclusions import ExclusionFilter
from daimon.motor.audit import AppendOnlyLedger
from daimon.motor.guard import PolicyGuard
from daimon.motor.organ import MotorOrgan
from daimon.motor.types import Level
from daimon.pacte.actuator import CooperativeActuator
from daimon.pacte.client import CooperativeClient
from daimon.pacte.gate import CooperativeGate
from daimon.pacte.organ import Pacte
from daimon.pacte.session import CooperativeSession
from tests.fakes.cooperative_endpoint import FakeCooperativeEndpoint


class _Recorder:
    """Captures registered tools so a test can call them directly."""
    def __init__(self): self.tools = {}
    def tool(self, name=None, description=None):
        def deco(fn): self.tools[name] = fn; return fn
        return deco


class _NullProber:
    def observe(self, action): return action.target


def _exclusions():
    return ExclusionFilter(ExclusionConfig(window_titles=[r"1Password"]))


def _build(tmp_path, fake_ep):
    exclusions = _exclusions()
    led = AppendOnlyLedger(tmp_path / "c.jsonl")
    session = CooperativeSession(led, clock=lambda: "ts")

    def motor_factory(client):
        guard = PolicyGuard(exclusions, ceiling_provider=session.ceiling)
        return MotorOrgan(guard=guard, gate=CooperativeGate(session),
                          actuator=CooperativeActuator(client),
                          session_log=led, clock=lambda: "ts", prober=_NullProber())

    return Pacte(exclusions, session, motor_factory,
                 discover_fn=lambda _d: fake_ep, cooperative_dir=tmp_path)


def test_describe_reports_disconnected_when_no_endpoint(tmp_path):
    p = Pacte(_exclusions(), CooperativeSession(AppendOnlyLedger(tmp_path / "c.jsonl"), lambda: "ts"),
              lambda c: None, discover_fn=lambda _d: None, cooperative_dir=tmp_path)
    rec = _Recorder(); p.register(rec)
    assert rec.tools["pacte_describe"]()["connected"] is False


def test_act_drag_within_ceiling_executes(tmp_path):
    fake = FakeCooperativeEndpoint(token="secret")
    fake.handlers["describe"] = lambda p: {"act_verbs": [{"name": "drag", "level": 2}]}
    fake.handlers["act"] = lambda p: {"ok": True, "verb": p["verb"]}
    ep = fake.start()
    try:
        from daimon.pacte.discovery import Endpoint
        p = _build(tmp_path, Endpoint(port=ep.port, token="secret", pid=1, app="delta", protocol_version="1.0"))
        rec = _Recorder(); p.register(rec)
        assert rec.tools["pacte_describe"]()["connected"] is True
        out = rec.tools["pacte_act"](verb="drag", args={"target": "n1"}, intent="move", level=2)
        assert out["status"] == "done" and out["result"]["ok"] is True
    finally:
        fake.stop()


def test_act_above_session_ceiling_is_refused(tmp_path):
    fake = FakeCooperativeEndpoint(token="secret")
    fake.handlers["describe"] = lambda p: {"act_verbs": []}
    ep = fake.start()
    try:
        from daimon.pacte.discovery import Endpoint
        p = _build(tmp_path, Endpoint(port=ep.port, token="secret", pid=1, app="delta", protocol_version="1.0"))
        rec = _Recorder(); p.register(rec)
        rec.tools["pacte_describe"]()
        out = rec.tools["pacte_act"](verb="wipe", args={}, intent="x", level=int(Level.AUTONOMOUS))
        assert out["status"] == "refused"
    finally:
        fake.stop()


def test_probe_redacts_excluded_titles(tmp_path):
    fake = FakeCooperativeEndpoint(token="secret")
    fake.handlers["describe"] = lambda p: {"act_verbs": []}
    fake.handlers["probe"] = lambda p: {"items": [{"id": "a", "title": "1Password vault"}, {"id": "b", "title": "canvas"}]}
    ep = fake.start()
    try:
        from daimon.pacte.discovery import Endpoint
        p = _build(tmp_path, Endpoint(port=ep.port, token="secret", pid=1, app="delta", protocol_version="1.0"))
        rec = _Recorder(); p.register(rec)
        rec.tools["pacte_describe"]()
        out = rec.tools["pacte_probe"]()
        ids = [it["id"] for it in out["items"]]
        assert ids == ["b"]   # the 1Password-titled item is pruned
    finally:
        fake.stop()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_pacte_organ.py -v`
Expected: FAIL with import error for `daimon.pacte.organ`

- [ ] **Step 3: Write minimal implementation**

```python
# src/daimon/pacte/organ.py
"""Pacte — the cooperative channel organ. Generic: speaks the protocol, never imports Qt.

pacte_describe handshakes + opens a cooperative session; pacte_probe reads redacted state;
pacte_act runs each verb through the SAME MotorOrgan chokepoint (ceiling + ledger), satisfied
by the durable session consent rather than a per-action dialog.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..exclusions import ExclusionFilter
from ..motor.organ import MotorOrgan
from ..motor.types import Declaration, Level, MotorAction, Target
from .client import CooperativeClient
from .discovery import discover
from .session import CooperativeSession

# Probe payload keys that carry node-shaped lists to run through redaction.
_NODE_LISTS = ("items", "decorators", "selected")


class Pacte:
    """Registers pacte_describe/probe/act; wires the cooperative client into the motor gate."""

    def __init__(self, exclusions: ExclusionFilter, session: CooperativeSession,
                 motor_organ_factory: Callable[[CooperativeClient], MotorOrgan],
                 discover_fn=discover, cooperative_dir: Path | None = None) -> None:
        self._exclusions = exclusions
        self._session = session
        self._motor_factory = motor_organ_factory
        self._discover = discover_fn
        self._dir = cooperative_dir
        self._client: CooperativeClient | None = None
        self._organ: MotorOrgan | None = None

    def register(self, mcp) -> None:
        @mcp.tool(name="pacte_describe", description=(
            "Connect to a cooperating app's --dev endpoint and return its capability manifest "
            "(probe fields + act verbs with their Hands level). Opens a cooperative session."))
        def pacte_describe() -> dict:
            ep = self._discover(self._dir)
            if ep is None:
                self._client = self._organ = None
                return {"connected": False, "reason": "no cooperative app found (launch it with --dev)"}
            self._client = CooperativeClient(ep)
            self._organ = self._motor_factory(self._client)
            self._session.open(app=ep.app, pid=ep.pid)
            manifest = self._client.call("describe", {})
            return {"connected": True, "app": ep.app, "manifest": manifest}

        @mcp.tool(name="pacte_probe", description=(
            "Read the cooperating app's internal state (selected ids, item geometries, undo depth, "
            "dirty flag, decorators). Read-only; secret-zone items are redacted."))
        def pacte_probe(fields: list[str] | None = None) -> dict:
            if self._client is None:
                return {"status": "refused", "reason": "no cooperative session (call pacte_describe first)"}
            payload = self._client.call("probe", {"fields": fields} if fields else {})
            for key in _NODE_LISTS:
                if isinstance(payload.get(key), list):
                    payload[key] = self._exclusions.redact_nodes(payload[key])
            return payload

        @mcp.tool(name="pacte_act", description=(
            "Invoke an app verb (drag/resize/marquee/click/load_fixture/shortcut). Routed through "
            "Daimon's Hands ceiling + audit ledger; pass the verb's declared level. Refused outside "
            "an open cooperative session or above the session ceiling."))
        def pacte_act(verb: str, args: dict, intent: str, level: int, reversible: bool = True) -> dict:
            if self._organ is None:
                return {"status": "refused", "reason": "no cooperative session (call pacte_describe first)"}
            action = MotorAction(
                name=verb, level=Level(level), target=Target(observed=True),
                declaration=Declaration(reversible=reversible, intent=intent),
                params={"args": args},
            )
            return self._organ.act(action)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_pacte_organ.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add src/daimon/pacte/organ.py tests/test_pacte_organ.py
git commit -m "feat(pacte): organ wiring describe/probe/act through the motor chokepoint"
```

---

### Task 7: Factory + server registration

**Files:**
- Create: `src/daimon/pacte/factory.py`
- Modify: `src/daimon/server.py` (add `_register_pacte(mcp)` + call it where `_register_motor`/`_register_overlay` are called)
- Test: `tests/test_pacte_factory.py`

**Interfaces:**
- Consumes: `build_consent` (for the config ceiling) and per-platform backends from `daimon.motor.factory`; `ExclusionFilter`; `AppendOnlyLedger`; `Pacte`, `CooperativeSession`, `CooperativeActuator`, `CooperativeGate`, `PolicyGuard`, `MotorOrgan`; `cooperative_dir()` (new, in `daimon.userdata`).
- Produces:
  - `daimon/userdata.py`: add `def cooperative_dir() -> Path` → `config_dir().parent / "cooperative"` i.e. `~/.daimon/cooperative` (create on demand). [If `userdata` already roots at `~/.daimon`, return `<root>/cooperative` — match the existing rooting; see `config_dir`/`logs_dir` in that file.]
  - `pacte/factory.py`: `def build_pacte() -> Pacte` — assembles `ExclusionFilter` (from `load_config().exclusions`), a `CooperativeSession` on a `cooperative.jsonl` ledger, and a `motor_organ_factory(client)` that builds a `PolicyGuard(exclusions, ceiling_provider=session.ceiling)` + `MotorOrgan(guard, gate=CooperativeGate(session), actuator=CooperativeActuator(client), session_log=<cooperative ledger>, clock=_now, prober=<null prober that returns the action target unchanged>)`. Uses `cooperative_dir()` for discovery.
  - `server.py`: `_register_pacte(mcp)` calls `build_pacte().register(mcp)`, wrapped so a construction failure logs and no-ops (never breaks server startup); invoked alongside the other registrations.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pacte_factory.py
from daimon.pacte.factory import build_pacte
from daimon.pacte.organ import Pacte


def test_build_pacte_returns_registerable_organ():
    p = build_pacte()
    assert isinstance(p, Pacte)


def test_build_pacte_registers_three_tools():
    class Rec:
        def __init__(self): self.names = []
        def tool(self, name=None, description=None):
            self.names.append(name)
            def deco(fn): return fn
            return deco
    rec = Rec()
    build_pacte().register(rec)
    assert set(rec.names) == {"pacte_describe", "pacte_probe", "pacte_act"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_pacte_factory.py -v`
Expected: FAIL with import error for `daimon.pacte.factory`

- [ ] **Step 3: Write the factory, the userdata helper, and the null prober**

First read `src/daimon/userdata.py` to match the existing root, then add:

```python
# src/daimon/userdata.py  (add this function, matching how config_dir/logs_dir root ~/.daimon)
def cooperative_dir() -> Path:
    """Where cooperating apps drop their --dev discovery files (~/.daimon/cooperative)."""
    d = config_dir().parent / "cooperative"  # adjust to the existing ~/.daimon root if different
    d.mkdir(parents=True, exist_ok=True)
    return d
```

```python
# src/daimon/pacte/factory.py
"""Build a fully-wired Pacte organ from config + real per-platform pieces."""

from __future__ import annotations

from datetime import datetime, timezone

from ..config import load_config
from ..exclusions import ExclusionFilter
from ..motor.audit import AppendOnlyLedger
from ..motor.factory import build_consent
from ..motor.guard import PolicyGuard
from ..motor.organ import MotorOrgan
from ..motor.types import MotorAction
from ..userdata import cooperative_dir, logs_dir
from .actuator import CooperativeActuator
from .client import CooperativeClient
from .gate import CooperativeGate
from .organ import Pacte
from .session import CooperativeSession


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class _PassThroughProber:
    """The cooperating endpoint is authoritative for the target; no OS observation here."""

    def observe(self, action: MotorAction):
        return action.target


def build_pacte() -> Pacte:
    """Assemble the Pacte organ: discovery + redaction + session-gated motor chokepoint."""
    exclusions = ExclusionFilter(load_config().exclusions)
    logs = logs_dir()
    logs.mkdir(parents=True, exist_ok=True)
    ledger = AppendOnlyLedger(logs / "cooperative.jsonl")
    session = CooperativeSession(ledger, clock=_now)

    def motor_factory(client: CooperativeClient) -> MotorOrgan:
        guard = PolicyGuard(exclusions, ceiling_provider=session.ceiling)
        return MotorOrgan(
            guard=guard, gate=CooperativeGate(session),
            actuator=CooperativeActuator(client),
            session_log=ledger, clock=_now, prober=_PassThroughProber(),
        )

    return Pacte(exclusions, session, motor_factory, cooperative_dir=cooperative_dir())
```

- [ ] **Step 4: Run the factory test**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_pacte_factory.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Wire into the server**

In `src/daimon/server.py`, add (mirroring `_register_overlay`/`_register_motor`):

```python
def _register_pacte(mcp) -> None:
    """Wire the optional cooperative channel tools; never break startup if unavailable."""
    try:
        from .pacte.factory import build_pacte
        build_pacte().register(mcp)
    except Exception:  # cooperative channel is optional; a build failure must not kill the server
        pass
```

Then call `_register_pacte(mcp)` next to the existing `_register_motor(mcp)` / `_register_overlay(mcp)` calls (find them in the server's build/serve function).

- [ ] **Step 6: Run the full suite**

Run: `/Users/Ben/.hfenv/bin/pytest -q`
Expected: all pass (existing suite + new `tests/test_pacte_*` green; no regressions)

- [ ] **Step 7: Commit**

```bash
git add src/daimon/pacte/factory.py src/daimon/userdata.py src/daimon/server.py tests/test_pacte_factory.py
git commit -m "feat(pacte): factory + server registration for the cooperative channel"
```

---

### Task 8: Server instructions + docs

**Files:**
- Modify: `src/daimon/senses/delegation.py` (server instructions string) — add a one-paragraph mention of `pacte_*` if the instructions enumerate tools. *(Read it first; if it does not enumerate per-tool, skip the edit.)*
- Modify: `README.md` — add `Pacte` to the organ list (Vue/Touché/Mains/Overlay → + Pacte cooperative channel), one sentence.
- Test: none (docs).

- [ ] **Step 1: Read `src/daimon/senses/delegation.py`** and check whether server instructions list tools by organ. If yes, add: "Pacte (cooperative channel): pacte_describe/pacte_probe/pacte_act drive and observe an app that exposes a --dev endpoint — generic, app-agnostic; acts go through the same Hands ceiling + ledger."

- [ ] **Step 2: Update `README.md`** organ list with one Pacte sentence.

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "docs(pacte): document the cooperative channel organ"
```

---

## Self-Review (completed)

**Spec coverage:** protocol → T1; transport+discovery+token → T2,T3; the two generic tools + 6-verb mapping (verbs are data passed to `pacte_act`/returned by `describe`, not Daimon code — covered by T6's `act`/`probe`) → T6; security (gate via `MotorOrgan`, durable consent, redaction, loopback+token) → T4,T5,T6; Fake endpoint testing → T3 and reused T5–T6; factory/registration → T7; docs → T8. The Delta-side endpoint is explicitly out of scope (separate contract doc). No gaps.

**Placeholder scan:** one deliberate adjust-to-existing note in T7 (`cooperative_dir` rooting) — gated on reading `userdata.py`, with the fallback expression given. No TBD/TODO in code steps.

**Type consistency:** `Endpoint`, `CooperativeClient.call`, `CooperativeSession.ceiling()/active()/open()`, `CooperativeGate.confirm`, `CooperativeActuator.execute`, `MotorAction` fields, `redact_nodes` usage match across tasks.
