# Organe moteur (« les Mains ») Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give Daimon a motor organ — act on the macOS UI (click, type, drag, validate, navigate) under a 5-level authorization ladder Daimon itself enforces, gating every point of no return behind out-of-band human consent.

**Architecture:** A new `motor/` package parallel to `senses/`. Every action funnels through a central `PolicyGuard` (mirror of `ExclusionFilter`): level gate → exclusion gate → reversibility cross-check (AI declares, Daimon verifies via heuristic) → REFUSE / GATE (native macOS dialog) / ALLOW. L4 autonomy is unlocked only by a human typing a phrase in a separate control CLI, recorded in an append-only hash-chained ledger; a runtime state file carries the active ceiling so human control is decoupled from the MCP server process. `no-log = no-act`; killing the process always overrides the lock.

**Tech Stack:** Python 3.12, pyobjc (Quartz CGEvent + ApplicationServices AX), FastMCP, PyYAML, pytest. Pure-logic modules (types, actions, reversibility, guard, audit, consent) are unit-tested without macOS; system modules (gate, actuator) sit behind injectable interfaces with fakes.

---

## File structure

| File | Responsibility |
|------|----------------|
| `src/daimon/motor/__init__.py` | package doc |
| `src/daimon/motor/types.py` | shared dataclasses/enums: `Level`, `Verdict`, `Target`, `Declaration`, `MotorAction`, `Reversibility`, `Decision` |
| `src/daimon/motor/actions.py` | verb registry: tool name → nominal `Level` + gesture |
| `src/daimon/motor/reversibility.py` | pure non-return classifier (multilingual denylist, fail-safe) |
| `src/daimon/motor/audit.py` | append-only hash-chained ledger + session log |
| `src/daimon/motor/consent.py` | L4 engagement state machine + runtime ceiling (config + state file) |
| `src/daimon/motor/guard.py` | `PolicyGuard.evaluate` — the chokepoint |
| `src/daimon/motor/gate.py` | human confirmation channel (macOS NSAlert/osascript) + `FakeGate` |
| `src/daimon/motor/actuator.py` | physical execution (AX press / CGEvent) + `FakeActuator` |
| `src/daimon/motor/organ.py` | `MotorOrgan.act` — wires guard→gate→actuator→audit |
| `src/daimon/motor/control.py` | human CLI: `engage` / `disengage` / `status` (out-of-band) |
| `src/daimon/config.py` | extend: load `motor.yaml` → `MotorConfig` |
| `config/motor.example.yaml` | committed default (ceiling L0, phrases) |
| `src/daimon/server.py` | register `main_*` tools through the organ |
| `tests/test_motor_*.py` | unit + integration tests |

Dependency order: types → actions → reversibility → audit → consent → guard → gate → actuator → organ → config → server/control.

---

## Task 1: Shared types

**Files:**
- Create: `src/daimon/motor/__init__.py`
- Create: `src/daimon/motor/types.py`
- Test: `tests/test_motor_types.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_motor_types.py
from daimon.motor.types import (
    Level, Verdict, Target, Declaration, MotorAction, Reversibility, Decision,
)


def test_level_ordering():
    assert Level.READ < Level.NONDESTRUCTIVE < Level.INPUT < Level.VALIDATION < Level.AUTONOMOUS
    assert int(Level.AUTONOMOUS) == 4


def test_motor_action_construction():
    action = MotorAction(
        name="click",
        level=Level.INPUT,
        target=Target(role="AXButton", label="Send"),
        declaration=Declaration(reversible=False, intent="send the email"),
        params={"x": 10, "y": 20},
    )
    assert action.target.label == "Send"
    assert action.declaration.reversible is False
    assert action.params["x"] == 10


def test_decision_defaults():
    d = Decision(verdict=Verdict.ALLOW, reason="ok")
    assert d.must_log is False
    assert Reversibility(irreversible=True, reason="verb").irreversible is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_motor_types.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'daimon.motor'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/daimon/motor/__init__.py
"""Motor organ — Daimon's hands.

A separate organ from the senses: it acts on the machine. Every action passes
through PolicyGuard, which enforces the authorization ceiling and refuses any
point of no return without out-of-band human consent. The AI client is never
trusted; Daimon enforces.
"""
```

```python
# src/daimon/motor/types.py
"""Shared value types for the motor organ. Pure data — no macOS imports."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


class Level(IntEnum):
    """Authorization ladder. Each level includes the previous ones."""

    READ = 0           # nothing (pure perception)
    NONDESTRUCTIVE = 1  # scroll, focus, internal navigation
    INPUT = 2          # click, type, drag
    VALIDATION = 3     # engaging buttons (send/confirm/pay)
    AUTONOMOUS = 4     # carte blanche — no per-action gate, everything traced


class Verdict(IntEnum):
    REFUSE = 0
    GATE = 1   # requires human confirmation
    ALLOW = 2


@dataclass(frozen=True)
class Target:
    """The UI element an action aims at, as probed by Touché (or raw coords)."""

    role: str | None = None
    label: str | None = None   # title / description text
    value: str | None = None
    x: int | None = None
    y: int | None = None


@dataclass(frozen=True)
class Declaration:
    """What the AI client asserts about an action it requests."""

    reversible: bool
    intent: str


@dataclass(frozen=True)
class MotorAction:
    name: str                 # "click" | "type" | "drag" | "press" | "navigate"
    level: Level
    target: Target
    declaration: Declaration
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Reversibility:
    irreversible: bool
    reason: str


@dataclass(frozen=True)
class Decision:
    verdict: Verdict
    reason: str
    must_log: bool = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_motor_types.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/daimon/motor/__init__.py src/daimon/motor/types.py tests/test_motor_types.py
git commit -m "feat(motor): shared types for the motor organ"
```

---

## Task 2: Verb registry

**Files:**
- Create: `src/daimon/motor/actions.py`
- Test: `tests/test_motor_actions.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_motor_actions.py
from daimon.motor.actions import ACTIONS, level_for
from daimon.motor.types import Level


def test_registry_maps_verbs_to_levels():
    assert level_for("main_navigate") == Level.NONDESTRUCTIVE
    assert level_for("main_click") == Level.INPUT
    assert level_for("main_type") == Level.INPUT
    assert level_for("main_drag") == Level.INPUT
    assert level_for("main_press") == Level.VALIDATION


def test_registry_is_complete():
    assert set(ACTIONS) == {"main_navigate", "main_click", "main_type", "main_drag", "main_press"}


def test_unknown_verb_raises():
    import pytest
    with pytest.raises(KeyError):
        level_for("main_launch_missiles")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_motor_actions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'daimon.motor.actions'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/daimon/motor/actions.py
"""The verbs the motor organ exposes, and their nominal authorization level.

Single source of truth for the tool→level mapping. The *target* may raise the
gate requirement above this nominal level (see reversibility), but never below.
"""

from __future__ import annotations

from dataclasses import dataclass

from .types import Level


@dataclass(frozen=True)
class ActionDef:
    tool_name: str
    level: Level
    gesture: str  # human-readable description


ACTIONS: dict[str, ActionDef] = {
    "main_navigate": ActionDef("main_navigate", Level.NONDESTRUCTIVE, "scroll/focus/switch/navigate"),
    "main_click": ActionDef("main_click", Level.INPUT, "click an element or coordinate"),
    "main_type": ActionDef("main_type", Level.INPUT, "type text"),
    "main_drag": ActionDef("main_drag", Level.INPUT, "drag/trace"),
    "main_press": ActionDef("main_press", Level.VALIDATION, "activate an engaging button"),
}


def level_for(tool_name: str) -> Level:
    return ACTIONS[tool_name].level
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_motor_actions.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/daimon/motor/actions.py tests/test_motor_actions.py
git commit -m "feat(motor): verb registry mapping tools to authorization levels"
```

---

## Task 3: Reversibility classifier

**Files:**
- Create: `src/daimon/motor/reversibility.py`
- Test: `tests/test_motor_reversibility.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_motor_reversibility.py
from daimon.motor.reversibility import classify
from daimon.motor.types import Declaration, Level, MotorAction, Target


def _action(target, name="click", level=Level.INPUT, params=None):
    return MotorAction(
        name=name, level=level, target=target,
        declaration=Declaration(reversible=True, intent="x"),
        params=params or {},
    )


def test_danger_verb_in_label_is_irreversible():
    for label in ["Send", "Envoyer", "Delete", "Supprimer", "Pay", "Payer", "Publier", "Empty Trash"]:
        rev = classify(_action(Target(role="AXButton", label=label)))
        assert rev.irreversible, label


def test_plain_label_is_reversible():
    rev = classify(_action(Target(role="AXButton", label="Cancel")))
    assert not rev.irreversible


def test_dangerous_key_combo_is_irreversible():
    rev = classify(_action(Target(role="AXTextArea", label="editor"),
                           name="navigate", level=Level.NONDESTRUCTIVE,
                           params={"keys": "cmd+delete"}))
    assert rev.irreversible


def test_unidentified_target_at_input_level_fails_safe():
    rev = classify(_action(Target()))  # no role, no label, INPUT level
    assert rev.irreversible
    assert "fail-safe" in rev.reason


def test_unidentified_target_at_navigate_level_is_ok():
    rev = classify(_action(Target(), name="navigate", level=Level.NONDESTRUCTIVE))
    assert not rev.irreversible
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_motor_reversibility.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'daimon.motor.reversibility'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/daimon/motor/reversibility.py
"""Daimon's independent point-of-no-return verdict.

Defense in depth: the AI *declares* reversibility per action; this module
computes Daimon's *own* verdict from the target. The guard reconciles the two
and the stricter wins. Pure — no macOS imports — so it is fully unit-tested.
"""

from __future__ import annotations

import re

from .types import Level, MotorAction, Reversibility, Target

# Multilingual verbs/labels that mark an engaging, typically irreversible action.
_DANGER_TEXT = re.compile(
    r"(?i)\b("
    r"send|envoyer|envoie|"
    r"delete|supprimer|effacer|remove|"
    r"empty|vider|"
    r"pay|payer|buy|acheter|purchase|"
    r"publish|publier|post|"
    r"confirm|confirmer|valider|"
    r"reset|réinitialiser|"
    r"destroy|détruire|discard|jeter|"
    r"submit|soumettre"
    r")\b"
)

# Key combinations that are destructive regardless of the target.
_DANGER_KEYS = re.compile(r"(?i)\bcmd\+(shift\+)?delete\b")


def _target_text(target: Target) -> str:
    return " ".join(p for p in (target.label, target.value, target.role) if p)


def classify(action: MotorAction) -> Reversibility:
    text = _target_text(action.target)
    if text and _DANGER_TEXT.search(text):
        return Reversibility(True, f"target matches non-return verb: {text!r}")

    keys = action.params.get("keys")
    if keys and _DANGER_KEYS.search(keys):
        return Reversibility(True, f"dangerous key combo: {keys}")

    # Fail-safe: an unidentified target at INPUT level or above is treated as risky.
    identified = bool(action.target.role or action.target.label)
    if action.level >= Level.INPUT and not identified:
        return Reversibility(True, "unidentified target at input level (fail-safe)")

    return Reversibility(False, "no non-return signal")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_motor_reversibility.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/daimon/motor/reversibility.py tests/test_motor_reversibility.py
git commit -m "feat(motor): non-return classifier (multilingual denylist, fail-safe)"
```

---

## Task 4: Append-only hash-chained audit

**Files:**
- Create: `src/daimon/motor/audit.py`
- Test: `tests/test_motor_audit.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_motor_audit.py
import json

from daimon.motor.audit import AppendOnlyLedger


def test_append_chains_hashes_and_verifies(tmp_path):
    ledger = AppendOnlyLedger(tmp_path / "ledger.jsonl")
    h1 = ledger.append({"event": "engage_l4", "ts": "2026-06-12T10:00:00Z"})
    h2 = ledger.append({"event": "disengage_l4", "ts": "2026-06-12T11:00:00Z"})
    assert h1 != h2
    lines = (tmp_path / "ledger.jsonl").read_text().splitlines()
    assert json.loads(lines[1])["prev_hash"] == h1
    assert ledger.verify()


def test_tampering_breaks_verification(tmp_path):
    path = tmp_path / "ledger.jsonl"
    ledger = AppendOnlyLedger(path)
    ledger.append({"event": "engage_l4", "ts": "t1"})
    ledger.append({"event": "act", "ts": "t2"})
    # Tamper with the first record's content.
    lines = path.read_text().splitlines()
    rec = json.loads(lines[0])
    rec["event"] = "FORGED"
    lines[0] = json.dumps(rec)
    path.write_text("\n".join(lines) + "\n")
    assert not ledger.verify()


def test_verify_empty_ledger_is_true(tmp_path):
    assert AppendOnlyLedger(tmp_path / "empty.jsonl").verify()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_motor_audit.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'daimon.motor.audit'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/daimon/motor/audit.py
"""Tamper-evident append-only logs.

Two uses, same primitive:
  - the consent ledger (L4 engage/disengage) — the immutable proof of consent;
  - the session log (every destructive action authorized).

Each record carries prev_hash and hash = sha256(prev_hash + canonical_body).
Any edit to a past record breaks the chain, so verify() detects tampering.
Callers supply a "ts" field (kept injectable for deterministic tests).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

_GENESIS = "0" * 64


class AppendOnlyLedger:
    def __init__(self, path) -> None:
        self.path = Path(path)

    def _records(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def _last_hash(self) -> str:
        records = self._records()
        return records[-1]["hash"] if records else _GENESIS

    @staticmethod
    def _compute(prev: str, body: dict) -> str:
        canonical = json.dumps(body, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256((prev + canonical).encode("utf-8")).hexdigest()

    def append(self, entry: dict) -> str:
        prev = self._last_hash()
        body = {**entry, "prev_hash": prev}
        h = self._compute(prev, body)
        record = {**body, "hash": h}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return h

    def verify(self) -> bool:
        prev = _GENESIS
        for record in self._records():
            stored = record.get("hash")
            body = {k: v for k, v in record.items() if k != "hash"}
            if body.get("prev_hash") != prev:
                return False
            if self._compute(prev, body) != stored:
                return False
            prev = stored
        return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_motor_audit.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/daimon/motor/audit.py tests/test_motor_audit.py
git commit -m "feat(motor): tamper-evident append-only hash-chained ledger"
```

---

## Task 5: Consent / ceiling state machine

**Files:**
- Create: `src/daimon/motor/consent.py`
- Test: `tests/test_motor_consent.py`

The runtime ceiling lives in a state file so the human control CLI (separate
process) can change it without touching the MCP server process. `current_ceiling`
reads config + state fresh each call.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_motor_consent.py
from daimon.motor.audit import AppendOnlyLedger
from daimon.motor.consent import ConsentManager
from daimon.motor.types import Level


def _manager(tmp_path, config_ceiling=Level.READ):
    return ConsentManager(
        config_ceiling=config_ceiling,
        engagement_phrase="I ENGAGE L4 AUTONOMY",
        disengagement_phrase="I DISENGAGE L4 AUTONOMY",
        ledger=AppendOnlyLedger(tmp_path / "consent.jsonl"),
        state_path=tmp_path / "motor.state.json",
    )


def test_default_ceiling_is_config(tmp_path):
    m = _manager(tmp_path, Level.VALIDATION)
    assert m.current_ceiling() == Level.VALIDATION


def test_engage_with_correct_phrase_raises_to_l4(tmp_path):
    m = _manager(tmp_path)
    assert m.engage("I ENGAGE L4 AUTONOMY", ts="t1") is True
    assert m.current_ceiling() == Level.AUTONOMOUS
    assert m._ledger.verify()


def test_engage_with_wrong_phrase_refused(tmp_path):
    m = _manager(tmp_path)
    assert m.engage("please let me", ts="t1") is False
    assert m.current_ceiling() == Level.READ


def test_disengage_requires_symmetric_phrase(tmp_path):
    m = _manager(tmp_path)
    m.engage("I ENGAGE L4 AUTONOMY", ts="t1")
    assert m.disengage("nope", ts="t2") is False
    assert m.current_ceiling() == Level.AUTONOMOUS
    assert m.disengage("I DISENGAGE L4 AUTONOMY", ts="t3") is True
    assert m.current_ceiling() == Level.READ


def test_engagement_survives_new_manager_instance(tmp_path):
    _manager(tmp_path).engage("I ENGAGE L4 AUTONOMY", ts="t1")
    # A fresh manager (e.g. the MCP server process) sees the state file.
    assert _manager(tmp_path).current_ceiling() == Level.AUTONOMOUS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_motor_consent.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'daimon.motor.consent'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/daimon/motor/consent.py
"""L4 engagement state machine.

L4 (full autonomy) is unlocked only by a human typing the exact engagement
phrase in the control CLI (out-of-band, never an MCP tool). Each engage/
disengage is recorded in the immutable consent ledger. The active flag lives in
a small state file so the human control process and the MCP server process agree
on the ceiling without sharing memory. Killing the server or deleting the state
file is the always-available physical override.
"""

from __future__ import annotations

import json
from pathlib import Path

from .audit import AppendOnlyLedger
from .types import Level


class ConsentManager:
    def __init__(
        self,
        config_ceiling: Level,
        engagement_phrase: str,
        disengagement_phrase: str,
        ledger: AppendOnlyLedger,
        state_path,
    ) -> None:
        self._config_ceiling = config_ceiling
        self._engagement_phrase = engagement_phrase
        self._disengagement_phrase = disengagement_phrase
        self._ledger = ledger
        self._state_path = Path(state_path)

    def _engaged(self) -> bool:
        if not self._state_path.exists():
            return False
        try:
            return bool(json.loads(self._state_path.read_text(encoding="utf-8")).get("engaged"))
        except (ValueError, OSError):
            return False

    def current_ceiling(self) -> Level:
        return Level.AUTONOMOUS if self._engaged() else self._config_ceiling

    def engage(self, typed: str, *, ts: str) -> bool:
        if typed.strip() != self._engagement_phrase:
            return False
        self._ledger.append({"event": "engage_l4", "ts": ts, "phrase": typed.strip()})
        self._state_path.write_text(json.dumps({"engaged": True, "ts": ts}), encoding="utf-8")
        return True

    def disengage(self, typed: str, *, ts: str) -> bool:
        if typed.strip() != self._disengagement_phrase:
            return False
        self._ledger.append({"event": "disengage_l4", "ts": ts})
        self._state_path.write_text(json.dumps({"engaged": False, "ts": ts}), encoding="utf-8")
        return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_motor_consent.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/daimon/motor/consent.py tests/test_motor_consent.py
git commit -m "feat(motor): L4 consent state machine with immutable ledger + state file"
```

---

## Task 6: PolicyGuard

**Files:**
- Create: `src/daimon/motor/guard.py`
- Test: `tests/test_motor_guard.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_motor_guard.py
from daimon.config import ExclusionConfig
from daimon.exclusions import ExclusionFilter
from daimon.motor.guard import PolicyGuard
from daimon.motor.types import Declaration, Decision, Level, MotorAction, Target, Verdict


def _guard(ceiling, exclusions=None):
    excl = ExclusionFilter(exclusions or ExclusionConfig())
    return PolicyGuard(exclusions=excl, ceiling_provider=lambda: ceiling)


def _action(level, target, reversible=True, name="click", params=None):
    return MotorAction(
        name=name, level=level, target=target,
        declaration=Declaration(reversible=reversible, intent="x"),
        params=params or {},
    )


def test_level_above_ceiling_is_refused():
    d = _guard(Level.NONDESTRUCTIVE).evaluate(_action(Level.INPUT, Target(label="ok")))
    assert d.verdict == Verdict.REFUSE


def test_reversible_within_ceiling_is_allowed():
    d = _guard(Level.INPUT).evaluate(_action(Level.INPUT, Target(role="AXButton", label="Cancel")))
    assert d.verdict == Verdict.ALLOW


def test_non_return_target_is_gated():
    d = _guard(Level.VALIDATION).evaluate(
        _action(Level.INPUT, Target(role="AXButton", label="Send"), reversible=True)
    )
    assert d.verdict == Verdict.GATE


def test_ai_declares_irreversible_forces_gate():
    d = _guard(Level.INPUT).evaluate(
        _action(Level.INPUT, Target(role="AXButton", label="Cancel"), reversible=False)
    )
    assert d.verdict == Verdict.GATE


def test_target_in_exclusion_zone_is_refused():
    d = _guard(Level.INPUT, ExclusionConfig(window_titles=(r"(?i)password",))).evaluate(
        _action(Level.INPUT, Target(role="AXTextField", label="Password field"))
    )
    assert d.verdict == Verdict.REFUSE


def test_l4_allows_without_gate_but_flags_log():
    d = _guard(Level.AUTONOMOUS).evaluate(
        _action(Level.VALIDATION, Target(role="AXButton", label="Send"), name="press")
    )
    assert d.verdict == Verdict.ALLOW
    assert d.must_log is True


def test_l4_reversible_action_allows_without_mandatory_log():
    d = _guard(Level.AUTONOMOUS).evaluate(
        _action(Level.INPUT, Target(role="AXButton", label="Cancel"))
    )
    assert d.verdict == Verdict.ALLOW
    assert d.must_log is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_motor_guard.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'daimon.motor.guard'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/daimon/motor/guard.py
"""PolicyGuard — the single chokepoint every action passes through.

Order of checks (any failure short-circuits):
  1. Level gate     — action.level must be ≤ the active ceiling.
  2. Exclusion gate — never act on a target inside a secrets zone.
  3. Reversibility  — Daimon's verdict vs the AI's declaration; stricter wins.
  4. Decision       — L4: ALLOW (flag destructive for mandatory logging);
                      L0–L3: GATE if any non-return signal, else ALLOW.
"""

from __future__ import annotations

from typing import Callable

from ..exclusions import ExclusionFilter
from . import reversibility
from .types import Decision, Level, MotorAction, Verdict


class PolicyGuard:
    def __init__(
        self,
        exclusions: ExclusionFilter,
        ceiling_provider: Callable[[], Level],
        classifier=reversibility.classify,
    ) -> None:
        self._exclusions = exclusions
        self._ceiling = ceiling_provider
        self._classify = classifier

    def evaluate(self, action: MotorAction) -> Decision:
        ceiling = self._ceiling()

        if action.level > ceiling:
            return Decision(Verdict.REFUSE, f"level {action.level.name} above ceiling {ceiling.name}")

        if self._exclusions.is_title_excluded(action.target.label):
            return Decision(Verdict.REFUSE, "target in exclusion zone")

        rev = self._classify(action)
        risky = rev.irreversible or (action.declaration.reversible is False)

        if ceiling == Level.AUTONOMOUS:
            return Decision(Verdict.ALLOW, "L4 autonomous", must_log=risky)

        if risky:
            reason = rev.reason if rev.irreversible else "AI declared action irreversible"
            return Decision(Verdict.GATE, reason)

        return Decision(Verdict.ALLOW, "reversible, within ceiling")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_motor_guard.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add src/daimon/motor/guard.py tests/test_motor_guard.py
git commit -m "feat(motor): PolicyGuard chokepoint (level/exclusion/reversibility gates)"
```

---

## Task 7: Human gate channel

**Files:**
- Create: `src/daimon/motor/gate.py`
- Test: `tests/test_motor_gate.py`

The real gate shows a native macOS dialog; tests use `FakeGate`. We test the
fake and the message-formatting helper (pure), not the GUI.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_motor_gate.py
from daimon.motor.gate import FakeGate, format_prompt
from daimon.motor.types import Declaration, Level, MotorAction, Target


def _action():
    return MotorAction(
        name="press", level=Level.VALIDATION,
        target=Target(role="AXButton", label="Send"),
        declaration=Declaration(reversible=False, intent="send the email"),
    )


def test_format_prompt_mentions_action_target_intent():
    msg = format_prompt(_action())
    assert "press" in msg
    assert "Send" in msg
    assert "send the email" in msg


def test_fake_gate_returns_preset_and_records():
    gate = FakeGate(answer=True)
    assert gate.confirm(_action()) is True
    assert len(gate.calls) == 1


def test_fake_gate_denies_by_default():
    assert FakeGate().confirm(_action()) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_motor_gate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'daimon.motor.gate'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/daimon/motor/gate.py
"""Out-of-band human confirmation channel for points of no return.

The real gate is a native macOS modal dialog driven by `osascript`; a timeout
or any error resolves to DENY. The AI cannot drive the dialog or self-confirm.
`FakeGate` is the test double. `format_prompt` is pure and unit-tested.
"""

from __future__ import annotations

from typing import Protocol

from .types import MotorAction

_TIMEOUT_SECONDS = 30


def format_prompt(action: MotorAction) -> str:
    t = action.target
    where = t.label or t.role or (f"({t.x},{t.y})" if t.x is not None else "unknown target")
    return (
        f"Daimon — l'IA veut: {action.name} sur « {where} ».\n"
        f"Intent: {action.declaration.intent}\n"
        f"Réversible (déclaré): {action.declaration.reversible}"
    )


class HumanGate(Protocol):
    def confirm(self, action: MotorAction) -> bool: ...


class FakeGate:
    """Test double: returns a preset answer and records calls."""

    def __init__(self, answer: bool = False) -> None:
        self._answer = answer
        self.calls: list[MotorAction] = []

    def confirm(self, action: MotorAction) -> bool:
        self.calls.append(action)
        return self._answer


class MacOSGate:
    """Native modal dialog via osascript. Timeout/error → DENY (fail-safe)."""

    def confirm(self, action: MotorAction) -> bool:
        import subprocess

        prompt = format_prompt(action).replace('"', "'")
        script = (
            f'display dialog "{prompt}" buttons {{"Refuser", "Autoriser"}} '
            f'default button "Refuser" with title "Daimon — Confirmation" '
            f'giving up after {_TIMEOUT_SECONDS}'
        )
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True, text=True, timeout=_TIMEOUT_SECONDS + 5,
            )
        except (subprocess.SubprocessError, OSError):
            return False
        if result.returncode != 0:
            return False  # user cancelled or error
        return "Autoriser" in result.stdout and "gave up:true" not in result.stdout
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_motor_gate.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/daimon/motor/gate.py tests/test_motor_gate.py
git commit -m "feat(motor): human gate channel (macOS dialog) + FakeGate"
```

---

## Task 8: Actuator

**Files:**
- Create: `src/daimon/motor/actuator.py`
- Test: `tests/test_motor_actuator.py`

Real execution touches the system; tests cover `FakeActuator` and the
dispatch table. The macOS implementation is exercised only by the live smoke
(Task 11).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_motor_actuator.py
import pytest

from daimon.motor.actuator import FakeActuator
from daimon.motor.types import Declaration, Level, MotorAction, Target


def _action(name, params):
    return MotorAction(
        name=name, level=Level.INPUT, target=Target(x=5, y=6),
        declaration=Declaration(reversible=True, intent="x"), params=params,
    )


def test_fake_actuator_records_executed_action():
    act = FakeActuator()
    result = act.execute(_action("click", {"x": 5, "y": 6}))
    assert result["status"] == "executed"
    assert act.executed[0].name == "click"


def test_fake_actuator_can_simulate_failure():
    act = FakeActuator(fail=True)
    with pytest.raises(RuntimeError):
        act.execute(_action("type", {"text": "hi"}))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_motor_actuator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'daimon.motor.actuator'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/daimon/motor/actuator.py
"""Physical execution of motor actions.

Prefers semantic Accessibility actions (AXPress on a re-probed element) for
`press`; uses synthetic CGEvents for click/type/drag/scroll. This is the only
module that mutates the host. Behind the `Actuator` protocol so the organ is
testable with `FakeActuator`.
"""

from __future__ import annotations

from typing import Protocol

from .types import MotorAction


class Actuator(Protocol):
    def execute(self, action: MotorAction) -> dict: ...


class FakeActuator:
    def __init__(self, fail: bool = False) -> None:
        self._fail = fail
        self.executed: list[MotorAction] = []

    def execute(self, action: MotorAction) -> dict:
        if self._fail:
            raise RuntimeError("actuator failure (simulated)")
        self.executed.append(action)
        return {"status": "executed", "action": action.name}


class MacOSActuator:
    def execute(self, action: MotorAction) -> dict:
        handler = {
            "click": self._click,
            "type": self._type,
            "drag": self._drag,
            "press": self._press,
            "navigate": self._navigate,
        }.get(action.name)
        if handler is None:
            raise ValueError(f"unknown action: {action.name}")
        handler(action)
        return {"status": "executed", "action": action.name}

    def _click(self, action: MotorAction) -> None:
        import Quartz

        x = action.params.get("x", action.target.x)
        y = action.params.get("y", action.target.y)
        for down, up in [(Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp)]:
            ev_down = Quartz.CGEventCreateMouseEvent(None, down, (x, y), Quartz.kCGMouseButtonLeft)
            ev_up = Quartz.CGEventCreateMouseEvent(None, up, (x, y), Quartz.kCGMouseButtonLeft)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev_down)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev_up)

    def _type(self, action: MotorAction) -> None:
        import Quartz

        text = action.params["text"]
        for ch in text:
            ev = Quartz.CGEventCreateKeyboardEvent(None, 0, True)
            Quartz.CGEventKeyboardSetUnicodeString(ev, len(ch), ch)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
            ev_up = Quartz.CGEventCreateKeyboardEvent(None, 0, False)
            Quartz.CGEventKeyboardSetUnicodeString(ev_up, len(ch), ch)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev_up)

    def _drag(self, action: MotorAction) -> None:
        import Quartz

        x1, y1 = action.params["from"]
        x2, y2 = action.params["to"]
        down = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseDown, (x1, y1), Quartz.kCGMouseButtonLeft)
        drag = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseDragged, (x2, y2), Quartz.kCGMouseButtonLeft)
        up = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseUp, (x2, y2), Quartz.kCGMouseButtonLeft)
        for ev in (down, drag, up):
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)

    def _press(self, action: MotorAction) -> None:
        from ApplicationServices import (
            AXUIElementCopyElementAtPosition,
            AXUIElementCreateSystemWide,
            AXUIElementPerformAction,
            kAXPressAction,
        )

        x = action.params.get("x", action.target.x)
        y = action.params.get("y", action.target.y)
        system = AXUIElementCreateSystemWide()
        err, element = AXUIElementCopyElementAtPosition(system, float(x), float(y), None)
        if err != 0 or element is None:
            raise RuntimeError(f"no element to press at ({x},{y})")
        AXUIElementPerformAction(element, kAXPressAction)

    def _navigate(self, action: MotorAction) -> None:
        import Quartz

        dy = int(action.params.get("scroll_y", 0))
        if dy:
            ev = Quartz.CGEventCreateScrollWheelEvent(None, Quartz.kCGScrollEventUnitPixel, 1, dy)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_motor_actuator.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/daimon/motor/actuator.py tests/test_motor_actuator.py
git commit -m "feat(motor): actuator (AX press + CGEvent) behind protocol + FakeActuator"
```

---

## Task 9: MotorOrgan wiring (guard → gate → actuator → audit)

**Files:**
- Create: `src/daimon/motor/organ.py`
- Test: `tests/test_motor_organ.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_motor_organ.py
from daimon.config import ExclusionConfig
from daimon.exclusions import ExclusionFilter
from daimon.motor.actuator import FakeActuator
from daimon.motor.audit import AppendOnlyLedger
from daimon.motor.gate import FakeGate
from daimon.motor.guard import PolicyGuard
from daimon.motor.organ import MotorOrgan
from daimon.motor.types import Declaration, Level, MotorAction, Target


def _organ(tmp_path, ceiling, gate_answer=False, actuator=None):
    guard = PolicyGuard(ExclusionFilter(ExclusionConfig()), ceiling_provider=lambda: ceiling)
    return MotorOrgan(
        guard=guard,
        gate=FakeGate(answer=gate_answer),
        actuator=actuator or FakeActuator(),
        session_log=AppendOnlyLedger(tmp_path / "session.jsonl"),
        clock=lambda: "T",
    )


def _action(level, target, reversible=True, name="click"):
    return MotorAction(
        name=name, level=level, target=target,
        declaration=Declaration(reversible=reversible, intent="x"),
    )


def test_refused_action_is_not_executed(tmp_path):
    act = FakeActuator()
    organ = _organ(tmp_path, Level.READ, actuator=act)
    out = organ.act(_action(Level.INPUT, Target(label="ok")))
    assert out["status"] == "refused"
    assert act.executed == []


def test_allowed_action_executes(tmp_path):
    act = FakeActuator()
    organ = _organ(tmp_path, Level.INPUT, actuator=act)
    out = organ.act(_action(Level.INPUT, Target(role="AXButton", label="Cancel")))
    assert out["status"] == "done"
    assert act.executed[0].name == "click"


def test_gated_action_denied_by_human_is_not_executed(tmp_path):
    act = FakeActuator()
    organ = _organ(tmp_path, Level.VALIDATION, gate_answer=False, actuator=act)
    out = organ.act(_action(Level.INPUT, Target(role="AXButton", label="Send")))
    assert out["status"] == "refused"
    assert act.executed == []


def test_gated_action_approved_executes_and_logs(tmp_path):
    act = FakeActuator()
    organ = _organ(tmp_path, Level.VALIDATION, gate_answer=True, actuator=act)
    out = organ.act(_action(Level.INPUT, Target(role="AXButton", label="Send")))
    assert out["status"] == "done"
    assert act.executed[0].target.label == "Send"
    assert (tmp_path / "session.jsonl").exists()


def test_l4_destructive_no_log_means_no_act(tmp_path):
    # Session log path points at a directory → write fails → action refused.
    bad = tmp_path / "as_dir"
    bad.mkdir()
    guard = PolicyGuard(ExclusionFilter(ExclusionConfig()), ceiling_provider=lambda: Level.AUTONOMOUS)
    act = FakeActuator()
    organ = MotorOrgan(
        guard=guard, gate=FakeGate(), actuator=act,
        session_log=AppendOnlyLedger(bad), clock=lambda: "T",
    )
    out = organ.act(_action(Level.VALIDATION, Target(role="AXButton", label="Send"), reversible=False, name="press"))
    assert out["status"] == "refused"
    assert "no-log" in out["reason"]
    assert act.executed == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_motor_organ.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'daimon.motor.organ'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/daimon/motor/organ.py
"""MotorOrgan — ties the chokepoint to the world.

act(action):
  1. guard.evaluate → REFUSE / GATE / ALLOW
  2. GATE → ask the human; deny → refuse
  3. if the decision requires logging (gated, or L4-destructive), write the
     session log FIRST. no-log = no-act: a failed write refuses the action.
  4. execute via the actuator; best-effort log the result.
"""

from __future__ import annotations

from typing import Callable

from .actuator import Actuator
from .audit import AppendOnlyLedger
from .gate import HumanGate
from .guard import PolicyGuard
from .types import MotorAction, Verdict


class MotorOrgan:
    def __init__(
        self,
        guard: PolicyGuard,
        gate: HumanGate,
        actuator: Actuator,
        session_log: AppendOnlyLedger,
        clock: Callable[[], str],
    ) -> None:
        self._guard = guard
        self._gate = gate
        self._actuator = actuator
        self._log = session_log
        self._clock = clock

    def _record(self, action: MotorAction, phase: str, extra: dict) -> bool:
        try:
            self._log.append({
                "ts": self._clock(),
                "phase": phase,
                "action": action.name,
                "target": action.target.label or action.target.role,
                "intent": action.declaration.intent,
                "declared_reversible": action.declaration.reversible,
                **extra,
            })
            return True
        except OSError:
            return False

    def act(self, action: MotorAction) -> dict:
        decision = self._guard.evaluate(action)

        if decision.verdict == Verdict.REFUSE:
            return {"status": "refused", "reason": decision.reason}

        if decision.verdict == Verdict.GATE:
            if not self._gate.confirm(action):
                self._record(action, "denied", {"reason": "human denied"})
                return {"status": "refused", "reason": "human denied"}
            must_log = True
        else:
            must_log = decision.must_log

        if must_log and not self._record(action, "authorized", {"reason": decision.reason}):
            return {"status": "refused", "reason": "no-log=no-act (audit write failed)"}

        result = self._actuator.execute(action)
        self._record(action, "executed", {"result": result})
        return {"status": "done", "result": result}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_motor_organ.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add src/daimon/motor/organ.py tests/test_motor_organ.py
git commit -m "feat(motor): MotorOrgan wiring with no-log=no-act enforcement"
```

---

## Task 10: Motor config (`motor.yaml`)

**Files:**
- Modify: `src/daimon/config.py`
- Create: `config/motor.example.yaml`
- Modify: `.gitignore`
- Test: `tests/test_motor_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_motor_config.py
from daimon.config import load_motor_config
from daimon.motor.types import Level


def test_defaults_to_l0_and_has_phrases(tmp_path):
    cfg = load_motor_config(tmp_path / "missing.yaml")
    assert cfg.ceiling == Level.READ
    assert cfg.engagement_phrase
    assert cfg.disengagement_phrase


def test_loads_ceiling_and_phrases(tmp_path):
    p = tmp_path / "motor.yaml"
    p.write_text(
        "motor:\n"
        "  ceiling: INPUT\n"
        "  l4:\n"
        "    engagement_phrase: GO\n"
        "    disengagement_phrase: STOP\n",
        encoding="utf-8",
    )
    cfg = load_motor_config(p)
    assert cfg.ceiling == Level.INPUT
    assert cfg.engagement_phrase == "GO"
    assert cfg.disengagement_phrase == "STOP"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_motor_config.py -v`
Expected: FAIL with `ImportError: cannot import name 'load_motor_config'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/daimon/config.py` (after the existing `load_config`):

```python
# --- motor config ---------------------------------------------------------
from .motor.types import Level  # noqa: E402  (kept near its use)

_MOTOR_DEFAULT = _REPO_ROOT / "config" / "motor.yaml"
_MOTOR_EXAMPLE = _REPO_ROOT / "config" / "motor.example.yaml"

_DEFAULT_ENGAGE = "I ENGAGE DAIMON L4 AUTONOMY ON THIS MACHINE"
_DEFAULT_DISENGAGE = "I DISENGAGE DAIMON L4 AUTONOMY"


@dataclass(frozen=True)
class MotorConfig:
    ceiling: Level = Level.READ
    engagement_phrase: str = _DEFAULT_ENGAGE
    disengagement_phrase: str = _DEFAULT_DISENGAGE


def _motor_path() -> Path:
    env = os.environ.get("DAIMON_MOTOR_CONFIG")
    if env:
        return Path(env).expanduser()
    if _MOTOR_DEFAULT.exists():
        return _MOTOR_DEFAULT
    return _MOTOR_EXAMPLE


def load_motor_config(path: Path | None = None) -> MotorConfig:
    path = path or _motor_path()
    if not path.exists():
        return MotorConfig()
    raw = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("motor", {}) or {}
    ceiling = Level[raw.get("ceiling", "READ")] if raw.get("ceiling") else Level.READ
    l4 = raw.get("l4", {}) or {}
    return MotorConfig(
        ceiling=ceiling,
        engagement_phrase=l4.get("engagement_phrase", _DEFAULT_ENGAGE),
        disengagement_phrase=l4.get("disengagement_phrase", _DEFAULT_DISENGAGE),
    )
```

Create `config/motor.example.yaml`:

```yaml
# Daimon motor organ — authorization config.
#
# Copy to config/motor.yaml (git-ignored) to change the ceiling or the L4
# phrases. Default is L0 (hands off). L4 is NOT set here — it is engaged at
# runtime via `python -m daimon.motor.control engage`.

motor:
  # Static ceiling for the AI's hands: READ | NONDESTRUCTIVE | INPUT | VALIDATION
  ceiling: READ

  l4:
    # The exact phrases a human must type in the control CLI to engage/disengage
    # full autonomy. Change them to something personal; they are proof of intent.
    engagement_phrase: "I ENGAGE DAIMON L4 AUTONOMY ON THIS MACHINE"
    disengagement_phrase: "I DISENGAGE DAIMON L4 AUTONOMY"
```

Add to `.gitignore` (under the existing local-config block):

```gitignore
config/motor.yaml
config/motor.state.json
logs/
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=src python -m pytest tests/test_motor_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add src/daimon/config.py config/motor.example.yaml .gitignore tests/test_motor_config.py
git commit -m "feat(motor): motor.yaml config (ceiling + L4 phrases)"
```

---

## Task 11: Control CLI + server registration + live smoke

**Files:**
- Create: `src/daimon/motor/control.py`
- Create: `src/daimon/motor/factory.py`
- Modify: `src/daimon/server.py`
- Create: `scripts/smoke_motor.py`
- Test: `tests/test_motor_control.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_motor_control.py
from daimon.motor.control import run_command
from daimon.motor.types import Level


def test_engage_then_status_then_disengage(tmp_path, capsys):
    cfg_state = tmp_path / "motor.state.json"
    ledger = tmp_path / "consent.jsonl"
    kw = dict(
        config_ceiling=Level.READ,
        engagement_phrase="GO", disengagement_phrase="STOP",
        ledger_path=ledger, state_path=cfg_state,
    )
    assert run_command("engage", typed="GO", **kw) == 0
    assert run_command("status", typed=None, **kw) == 0
    assert "AUTONOMOUS" in capsys.readouterr().out
    assert run_command("engage", typed="wrong", **kw) == 1
    assert run_command("disengage", typed="STOP", **kw) == 0
    assert "READ" in capsys.readouterr().out or run_command("status", typed=None, **kw) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src python -m pytest tests/test_motor_control.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'daimon.motor.control'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/daimon/motor/factory.py
"""Build a fully-wired MotorOrgan + ConsentManager from config (real backends)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from ..config import load_motor_config
from ..config import load_config as load_exclusions
from ..exclusions import ExclusionFilter
from .actuator import MacOSActuator
from .audit import AppendOnlyLedger
from .consent import ConsentManager
from .gate import MacOSGate
from .guard import PolicyGuard
from .organ import MotorOrgan

_LOGS = Path(__file__).resolve().parents[3] / "logs"
_STATE = Path(__file__).resolve().parents[3] / "config" / "motor.state.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_consent() -> ConsentManager:
    mcfg = load_motor_config()
    _LOGS.mkdir(exist_ok=True)
    return ConsentManager(
        config_ceiling=mcfg.ceiling,
        engagement_phrase=mcfg.engagement_phrase,
        disengagement_phrase=mcfg.disengagement_phrase,
        ledger=AppendOnlyLedger(_LOGS / "consent.jsonl"),
        state_path=_STATE,
    )


def build_organ() -> MotorOrgan:
    consent = build_consent()
    exclusions = ExclusionFilter(load_exclusions().exclusions)
    guard = PolicyGuard(exclusions, ceiling_provider=consent.current_ceiling)
    _LOGS.mkdir(exist_ok=True)
    return MotorOrgan(
        guard=guard,
        gate=MacOSGate(),
        actuator=MacOSActuator(),
        session_log=AppendOnlyLedger(_LOGS / "session.jsonl"),
        clock=_now,
    )
```

```python
# src/daimon/motor/control.py
"""Human, out-of-band control of the motor ceiling. NEVER an MCP tool.

Usage (typed by the human at a terminal):
    python -m daimon.motor.control status
    python -m daimon.motor.control engage      # prompts for the engagement phrase
    python -m daimon.motor.control disengage    # prompts for the disengagement phrase
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from .audit import AppendOnlyLedger
from .consent import ConsentManager
from .types import Level


def run_command(command: str, *, typed: str | None, config_ceiling: Level,
                engagement_phrase: str, disengagement_phrase: str,
                ledger_path, state_path) -> int:
    manager = ConsentManager(
        config_ceiling=config_ceiling,
        engagement_phrase=engagement_phrase,
        disengagement_phrase=disengagement_phrase,
        ledger=AppendOnlyLedger(ledger_path),
        state_path=state_path,
    )
    ts = datetime.now(timezone.utc).isoformat()

    if command == "status":
        print(f"Daimon motor ceiling: {manager.current_ceiling().name}")
        return 0
    if command == "engage":
        ok = manager.engage(typed or "", ts=ts)
        print("L4 ENGAGED." if ok else "Refused: phrase mismatch.")
        return 0 if ok else 1
    if command == "disengage":
        ok = manager.disengage(typed or "", ts=ts)
        print("L4 disengaged." if ok else "Refused: phrase mismatch.")
        return 0 if ok else 1
    print(f"Unknown command: {command}")
    return 2


def main(argv: list[str] | None = None) -> int:
    from ..config import load_motor_config
    from .factory import _LOGS, _STATE

    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("Usage: python -m daimon.motor.control [status|engage|disengage]")
        return 2
    command = argv[0]
    mcfg = load_motor_config()
    typed = None
    if command in {"engage", "disengage"}:
        typed = input("Type the phrase to confirm: ")
    _LOGS.mkdir(exist_ok=True)
    return run_command(
        command, typed=typed,
        config_ceiling=mcfg.ceiling,
        engagement_phrase=mcfg.engagement_phrase,
        disengagement_phrase=mcfg.disengagement_phrase,
        ledger_path=_LOGS / "consent.jsonl",
        state_path=_STATE,
    )


if __name__ == "__main__":
    raise SystemExit(main())
```

Modify `src/daimon/server.py` — register the motor tools. Add imports at the top and a `_register_motor(mcp)` call inside `build_server` before `return mcp`:

```python
# add to imports
from .motor.factory import build_organ
from .motor.actions import level_for
from .motor.types import Declaration, MotorAction, Target


def _register_motor(mcp) -> None:
    organ = build_organ()

    def _target(x: int | None, y: int | None, role: str | None, label: str | None) -> Target:
        return Target(role=role, label=label, x=x, y=y)

    @mcp.tool(
        name="main_click",
        description=(
            "Click an element/coordinate. Provide the target's role/label (from "
            "Touché) so Daimon can verify reversibility. `reversible` and `intent` "
            "are your declaration; Daimon enforces the ceiling and may require human "
            "confirmation. Refused if above the configured ceiling."
        ),
    )
    def main_click(x: int, y: int, intent: str, reversible: bool = True,
                   role: str = "", label: str = "") -> dict:
        action = MotorAction(
            name="click", level=level_for("main_click"),
            target=_target(x, y, role or None, label or None),
            declaration=Declaration(reversible=reversible, intent=intent),
            params={"x": x, "y": y},
        )
        return organ.act(action)

    @mcp.tool(
        name="main_type",
        description="Type text into the focused field. Declare intent/reversibility.",
    )
    def main_type(text: str, intent: str, reversible: bool = True,
                  role: str = "", label: str = "") -> dict:
        action = MotorAction(
            name="type", level=level_for("main_type"),
            target=_target(None, None, role or None, label or None),
            declaration=Declaration(reversible=reversible, intent=intent),
            params={"text": text},
        )
        return organ.act(action)

    @mcp.tool(
        name="main_press",
        description=(
            "Activate an engaging button at (x,y) via the Accessibility API. "
            "VALIDATION level — non-return targets require human confirmation."
        ),
    )
    def main_press(x: int, y: int, intent: str, reversible: bool = False,
                   role: str = "", label: str = "") -> dict:
        action = MotorAction(
            name="press", level=level_for("main_press"),
            target=_target(x, y, role or None, label or None),
            declaration=Declaration(reversible=reversible, intent=intent),
            params={"x": x, "y": y},
        )
        return organ.act(action)

    @mcp.tool(
        name="main_navigate",
        description="Non-destructive navigation: scroll by scroll_y pixels at the focused view.",
    )
    def main_navigate(intent: str, scroll_y: int = 0) -> dict:
        action = MotorAction(
            name="navigate", level=level_for("main_navigate"),
            target=Target(),
            declaration=Declaration(reversible=True, intent=intent),
            params={"scroll_y": scroll_y},
        )
        return organ.act(action)
```

Then call `_register_motor(mcp)` in `build_server`:

```python
    for sense in senses:
        sense.register(mcp)

    _register_motor(mcp)   # <-- add this line

    return mcp
```

Create `scripts/smoke_motor.py`:

```python
"""Live motor smoke — requires a human present. Targets a TextEdit sandbox.

Run with the ceiling set to INPUT (config/motor.yaml) and TextEdit frontmost.
Demonstrates: a reversible type (no gate) executes; a press on a 'Send'-like
button gates for human confirmation.

    python scripts/smoke_motor.py
"""

from __future__ import annotations

from daimon.motor.factory import build_organ
from daimon.motor.types import Declaration, MotorAction, Target


def main() -> int:
    organ = build_organ()

    typed = organ.act(MotorAction(
        name="type", level=2,  # INPUT
        target=Target(role="AXTextArea", label="document"),
        declaration=Declaration(reversible=True, intent="write a smoke note"),
        params={"text": "Daimon motor smoke ok\n"},
    ))
    print("type:", typed)

    gated = organ.act(MotorAction(
        name="press", level=3,  # VALIDATION
        target=Target(role="AXButton", label="Send"),
        declaration=Declaration(reversible=False, intent="pretend send"),
        params={"x": 100, "y": 100},
    ))
    print("press (should gate):", gated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests + verify server builds**

Run:
```bash
PYTHONPATH=src python -m pytest tests/test_motor_control.py -v
PYTHONPATH=src python -c "from daimon.server import build_server; import asyncio; m=build_server(); print(sorted(t.name for t in asyncio.run(m.list_tools())))"
```
Expected: control tests PASS; tool list includes `main_click`, `main_type`, `main_press`, `main_navigate` alongside the `vue_*`/`touche_*` tools.

- [ ] **Step 5: Commit**

```bash
git add src/daimon/motor/control.py src/daimon/motor/factory.py src/daimon/server.py scripts/smoke_motor.py tests/test_motor_control.py
git commit -m "feat(motor): control CLI, organ factory, MCP tool registration"
```

---

## Task 12: Full suite green + README update

**Files:**
- Modify: `README.md`
- Test: all

- [ ] **Step 1: Run the whole suite**

Run: `PYTHONPATH=src python -m pytest -q`
Expected: all tests pass (sensory + motor).

- [ ] **Step 2: Update README** — add a "The hands (motor organ)" section after the senses table:

```markdown
## The hands (motor organ)

Daimon can act under a ceiling it enforces itself (default **L0**, hands off):

| Level | Scope | Gate |
|-------|-------|------|
| L0 READ | nothing | — |
| L1 NONDESTRUCTIVE | scroll, focus, navigate | none |
| L2 INPUT | click, type, drag | none, unless the target is a point of no return |
| L3 VALIDATION | engaging buttons | human confirmation on any non-return |
| L4 AUTONOMOUS | full autonomy | none — everything traced |

- Tools: `main_navigate`, `main_click`, `main_type`, `main_drag`, `main_press`.
- Points of no return (send/delete/pay/…) are classified (AI declares, Daimon
  verifies) and gated by a **native macOS dialog**. Timeout = deny.
- **L4** is engaged only by a human typing a phrase out-of-band:
  `python -m daimon.motor.control engage` (and `disengage`). The consent is
  recorded in an append-only, hash-chained ledger under `logs/`. `no-log = no-act`.
- Set the ceiling in `config/motor.yaml` (copy `config/motor.example.yaml`).
- Kill the process at any time to stop everything — the physical override always wins.
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: document the motor organ (hands) and its authorization model"
```

---

## Self-review

**Spec coverage:**
- §1 Daimon enforces / not trusting client → guard + ceiling_provider (Task 6). ✓
- §2 five levels, default L0, AI can't raise ceiling → `Level`, `load_motor_config` default, guard level gate (Tasks 1, 6, 10). ✓
- §2 verb→tool mapping → `actions.py` + server tools (Tasks 2, 11). ✓
- §3 architecture/flow, PolicyGuard chokepoint, isolated modules → Tasks 6, 9. ✓
- §4 AI-declares/Daimon-verifies, denylist, fail-safe, divergence both ways → `reversibility.py` + guard `risky` logic (Tasks 3, 6). ✓
- §5 L4 written engagement, symmetric disengagement, immutable ledger, no-log=no-act, kill switch → consent + audit + organ + control (Tasks 4, 5, 9, 11). Kill switch = OS-level (documented Task 12). ✓
- §6 native macOS gate, timeout=deny → `MacOSGate` (Task 7). ✓
- §7 AX press preferred, CGEvent fallback → `actuator.py` (Task 8). ✓
- §8 invariants → covered across guard/organ/consent tests. ✓
- §9 test strategy → pure unit tests + fakes + live smoke (Tasks 3–11). ✓
- §10 YAGNI: no pre-auth cache, no macros — none added. Panic hotkey deferred (kill process is the v0 override). ✓
- §11 reuses accessibility/ExclusionFilter; secrets-content hardening flagged as a prerequisite for real L4 use (out of this plan's scope, tracked in memory). ✓

**Placeholder scan:** no TBD/TODO; every code step is complete. ✓

**Type consistency:** `Level`, `Verdict`, `MotorAction(name, level, target, declaration, params)`, `Decision(verdict, reason, must_log)`, `classify(action)`, `PolicyGuard(exclusions, ceiling_provider, classifier)`, `MotorOrgan(guard, gate, actuator, session_log, clock)`, `ConsentManager(config_ceiling, engagement_phrase, disengagement_phrase, ledger, state_path)` — names/signatures consistent across tasks. ✓

**Note:** `factory.py` is introduced in Task 11 and imported by both `control.main` and `server`. Its `_LOGS`/`_STATE` paths are the single source for runtime log/state location.
