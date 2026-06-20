# Delegation-grade Motor Authorization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop gating benign keyboard/window actions, let the orchestrator learn its authorization envelope up-front, and make L4 autonomy engageable from the tray with an audited confirmation — so delegated UI-driving runs without spurious prompts.

**Architecture:** Three tightly-coupled changes to the motor authorization path. ① The guard's "unobserved target → gate" rule is scoped to actions that *commit on a screen target* (click/press/drag/mouse), driven by a new `ActionDef.requires_observed_target` flag. ② A pure `ceiling_report` plus a read-only `main_ceiling` MCP tool and a server-instructions note expose the active ceiling. ③ `ConsentManager.engage_confirmed` + new tray menu entries + an AppKit NSAlert let a human engage/disengage L4, recorded immutably in the consent ledger.

**Tech Stack:** Python 3.12, FastMCP, pyobjc/AppKit (tray only), pytest.

## Global Constraints

- Run the suite with: `/Users/Ben/.hfenv/bin/pytest -q` — must stay green (currently 374) and grow.
- Daimon enforces the ceiling; the guard stays the single chokepoint. No MCP tool may raise the ceiling — `main_ceiling` is read-only; L4 engagement is a human tray action, never a tool.
- The unobserved-target gate stays intact for positional commits; dangerous key combos still gate.
- L4 stays auditable + reversible: engage AND disengage are written to the consent ledger; `current_ceiling()` returns AUTONOMOUS only when the state flag AND the last ledger event (`engage_l4`) agree.
- No `print` at import/startup (MCP stdio). Server-instructions text stays agnostic (no model/brand name).
- `MotorAction.name` is the SHORT verb ("click", "key", …); the tool name is `"main_" + name` (regular). `ACTIONS` is keyed by the tool name.
- Conventional commits; end body with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: ① Scope the unobserved-target gate to positional commits

**Files:**
- Modify: `src/daimon/motor/actions.py` (add field to `ActionDef`, set per action, add helper)
- Modify: `src/daimon/motor/guard.py` (guard the observation branch)
- Test: `tests/test_motor_guard.py` (add cases), `tests/test_motor_actions.py` (add helper test)

**Interfaces:**
- Produces: `ActionDef.requires_observed_target: bool` (field, default True); `requires_observed_target(action_name: str) -> bool` in `motor/actions.py`, where `action_name` is the SHORT verb (e.g. "click"). Returns the flag for `ACTIONS["main_" + action_name]`, defaulting to True for unknown names.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_motor_actions.py — add
from daimon.motor.actions import requires_observed_target


def test_requires_observed_target_positional_vs_not():
    for verb in ("click", "press", "drag", "mouse_down", "mouse_up"):
        assert requires_observed_target(verb) is True
    for verb in ("key", "type", "key_down", "key_up", "activate", "hover", "navigate"):
        assert requires_observed_target(verb) is False
    assert requires_observed_target("unknown_verb") is True  # safe default
```

```python
# tests/test_motor_guard.py — add (reuse the file's existing helpers for building a guard/action;
# these use the public types directly so they stand alone)
from daimon.motor.guard import PolicyGuard
from daimon.motor.types import Level, MotorAction, Target, Verdict
from daimon.exclusions import ExclusionFilter


def _guard(ceiling=Level.VALIDATION, classifier=None):
    from daimon.motor import reversibility
    return PolicyGuard(ExclusionFilter([]), ceiling_provider=lambda: ceiling,
                       classifier=classifier or reversibility.classify)


def test_keyboard_action_not_gated_for_missing_observed_target():
    # A benign chord (cmd+M) with no observable target used to GATE; now it ALLOWs at L3.
    g = _guard(Level.VALIDATION)
    a = MotorAction(name="key", level=Level.INPUT, target=Target(observed=False),
                    params={"key": "m", "modifiers": ["cmd"]})
    assert g.evaluate(a).verdict == Verdict.ALLOW


def test_positional_click_still_gates_for_missing_observed_target():
    g = _guard(Level.VALIDATION)
    a = MotorAction(name="click", level=Level.INPUT, target=Target(x=10, y=10, observed=False))
    assert g.evaluate(a).verdict == Verdict.GATE


def test_dangerous_keyboard_combo_still_gates():
    # Force the classifier to mark the combo irreversible — the keyboard exemption must NOT
    # bypass combo classification.
    from daimon.motor.reversibility import Reversibility
    g = _guard(Level.VALIDATION, classifier=lambda a: Reversibility(irreversible=True, reason="dangerous combo"))
    a = MotorAction(name="key", level=Level.INPUT, target=Target(observed=False),
                    params={"key": "q", "modifiers": ["cmd"]})
    assert g.evaluate(a).verdict == Verdict.GATE
```

(If `Reversibility`'s field names differ, read `src/daimon/motor/reversibility.py` and match them; the test's intent is "classifier says irreversible → still GATE".)

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_motor_actions.py tests/test_motor_guard.py -q`
Expected: FAIL — `ImportError: cannot import name 'requires_observed_target'` and the keyboard case still GATEs.

- [ ] **Step 3: Implement**

```python
# src/daimon/motor/actions.py — add the field to the ActionDef dataclass
@dataclass
class ActionDef:
    """Maps an exposed tool verb to its nominal authorization level."""
    tool_name: str
    level: Level
    gesture: str
    requires_observed_target: bool = True  # False for acts with no screen target to verify
```

```python
# src/daimon/motor/actions.py — set the flag on the acts that do NOT commit on a screen target.
# Edit these existing entries to add requires_observed_target=False:
#   main_type, main_key, main_hover, main_activate, main_key_down, main_key_up, main_navigate
# e.g.:
    "main_key": ActionDef("main_key", Level.INPUT, "discrete key / chord", requires_observed_target=False),
    "main_type": ActionDef("main_type", Level.INPUT, "type text", requires_observed_target=False),
    "main_hover": ActionDef("main_hover", Level.NONDESTRUCTIVE, "move pointer only", requires_observed_target=False),
    "main_activate": ActionDef("main_activate", Level.NONDESTRUCTIVE, "bring app/window frontmost", requires_observed_target=False),
    "main_navigate": ActionDef("main_navigate", Level.NONDESTRUCTIVE, "scroll/focus/switch/navigate", requires_observed_target=False),
    "main_key_down": ActionDef("main_key_down", Level.AUTONOMOUS, "press and hold a key", requires_observed_target=False),
    "main_key_up": ActionDef("main_key_up", Level.AUTONOMOUS, "release a held key", requires_observed_target=False),
# (click, press, drag, mouse_down, mouse_up keep the default True.)
```

```python
# src/daimon/motor/actions.py — add near level_for()
def requires_observed_target(action_name: str) -> bool:
    """Whether the SHORT-named action commits on a screen target that must be verified.

    True (default) for positional commits (click/press/drag/mouse_*); False for keyboard,
    window-by-bundle, and pure pointer moves, which carry no target to observe.
    """
    spec = ACTIONS.get("main_" + action_name)
    return spec.requires_observed_target if spec else True
```

```python
# src/daimon/motor/guard.py — gate the observation branch (replace the existing block)
        if requires_observed_target(action.name) and not action.target.observed:
            if ceiling == Level.AUTONOMOUS:
                return Decision(Verdict.REFUSE, "target unobservable under L4 (no blind autonomous action)")
            return Decision(Verdict.GATE, "Daimon could not verify the target")
```

Add the import at the top of `guard.py`: `from .actions import requires_observed_target`.

- [ ] **Step 4: Run tests to verify they pass + full suite**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_motor_actions.py tests/test_motor_guard.py -q && /Users/Ben/.hfenv/bin/pytest -q`
Expected: PASS, full suite green.

- [ ] **Step 5: Commit**

```bash
git add src/daimon/motor/actions.py src/daimon/motor/guard.py tests/test_motor_actions.py tests/test_motor_guard.py
git commit -m "fix(motor): scope unobserved-target gate to positional commits (keyboard no longer gates)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: ② Pure ceiling_report + expose current_ceiling

**Files:**
- Modify: `src/daimon/motor/actions.py` (add `ceiling_report`)
- Modify: `src/daimon/motor/guard.py` (add `PolicyGuard.current_ceiling`)
- Modify: `src/daimon/motor/organ.py` (add `MotorOrgan.current_ceiling`)
- Test: `tests/test_motor_actions.py`, `tests/test_motor_guard.py`

**Interfaces:**
- Produces: `ceiling_report(current: Level) -> dict` → `{"ceiling": <NAME>, "l4_active": bool, "levels": {tool_name: level_name}, "gated_above": [tool_name,...]}`; `PolicyGuard.current_ceiling() -> Level`; `MotorOrgan.current_ceiling() -> Level`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_motor_actions.py — add
from daimon.motor.actions import ceiling_report
from daimon.motor.types import Level


def test_ceiling_report_at_validation():
    r = ceiling_report(Level.VALIDATION)
    assert r["ceiling"] == "VALIDATION"
    assert r["l4_active"] is False
    assert r["levels"]["main_click"] == "INPUT"
    # AUTONOMOUS-level primitives are above L3 → gated.
    assert "main_mouse_down" in r["gated_above"]
    # An INPUT-level act is within L3 → not gated.
    assert "main_click" not in r["gated_above"]


def test_ceiling_report_l4_active():
    assert ceiling_report(Level.AUTONOMOUS)["l4_active"] is True
    assert ceiling_report(Level.AUTONOMOUS)["gated_above"] == []
```

```python
# tests/test_motor_guard.py — add
def test_guard_exposes_current_ceiling():
    g = _guard(Level.INPUT)
    assert g.current_ceiling() == Level.INPUT
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_motor_actions.py tests/test_motor_guard.py -q`
Expected: FAIL — `ImportError: cannot import name 'ceiling_report'`, and `current_ceiling` missing.

- [ ] **Step 3: Implement**

```python
# src/daimon/motor/actions.py — add
def ceiling_report(current: Level) -> dict:
    """Read-only snapshot of the active ceiling and which tools it gates."""
    return {
        "ceiling": current.name,
        "l4_active": current == Level.AUTONOMOUS,
        "levels": {name: d.level.name for name, d in ACTIONS.items()},
        "gated_above": sorted(name for name, d in ACTIONS.items() if d.level > current),
    }
```

```python
# src/daimon/motor/guard.py — add a method on PolicyGuard
    def current_ceiling(self) -> Level:
        """The active ceiling (what the ceiling_provider currently returns)."""
        return self._ceiling()
```

```python
# src/daimon/motor/organ.py — add a method on MotorOrgan (self._guard is set in __init__)
    def current_ceiling(self):
        """Expose the active ceiling for read-only reporting (e.g. main_ceiling)."""
        return self._guard.current_ceiling()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_motor_actions.py tests/test_motor_guard.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/daimon/motor/actions.py src/daimon/motor/guard.py src/daimon/motor/organ.py tests/test_motor_actions.py tests/test_motor_guard.py
git commit -m "feat(motor): ceiling_report + expose current_ceiling (AXE ceiling awareness)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: ② `main_ceiling` read-only MCP tool

**Files:**
- Modify: `src/daimon/server.py` (register the tool inside `_register_motor`, where `organ` is in scope, ~line 94+)
- Test: `tests/test_server_tools.py`

**Interfaces:**
- Consumes: `MotorOrgan.current_ceiling()` (Task 2), `ceiling_report` (Task 2).
- Produces: MCP tool `main_ceiling() -> dict`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server_tools.py — add
def test_main_ceiling_is_registered():
    import asyncio
    names = {t.name for t in asyncio.run(build_server().list_tools())}
    assert "main_ceiling" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_server_tools.py::test_main_ceiling_is_registered -q`
Expected: FAIL — `main_ceiling` not in the tool set.

- [ ] **Step 3: Implement**

```python
# src/daimon/server.py — inside _register_motor(mcp), after `organ = build_organ()` and the
# other @mcp.tool registrations (organ is in closure scope):
    @mcp.tool(
        name="main_ceiling",
        description=(
            "Report the active Hands authorization ceiling and which tools it gates. "
            "Read-only — it never changes the ceiling. Check it before driving so you can "
            "declare up-front what you cannot do rather than being refused mid-flow. Returns "
            "{ceiling, l4_active, levels:{tool:level}, gated_above:[tools above the ceiling]}."
        ),
    )
    def main_ceiling() -> dict:
        from .motor.actions import ceiling_report
        return ceiling_report(organ.current_ceiling())
```

- [ ] **Step 4: Run test + full suite**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_server_tools.py::test_main_ceiling_is_registered -q && /Users/Ben/.hfenv/bin/pytest -q`
Expected: PASS, full suite green.

- [ ] **Step 5: Commit**

```bash
git add src/daimon/server.py tests/test_server_tools.py
git commit -m "feat(server): main_ceiling read-only tool exposes the active ceiling

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: ② Surface ceiling awareness in the delegation surfaces

**Files:**
- Modify: `src/daimon/senses/delegation.py` (add a Hands-ceiling note to the server-instructions; add a ceiling step to the sub-agent prompt)
- Test: `tests/test_delegation.py`

**Interfaces:**
- Consumes: `delegation_protocol_text()`, `build_server_instructions()`, `_subagent_prompt`/`pilot_brief` (all existing in delegation.py).
- Produces: updated `build_server_instructions()` text containing a `main_ceiling` reference; `_subagent_prompt` mentioning `main_ceiling`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_delegation.py — add (reuses the file's existing _BRANDS regex)
from daimon.senses.delegation import build_server_instructions, pilot_brief


def test_server_instructions_mention_hands_ceiling():
    instr = build_server_instructions()
    assert "main_ceiling" in instr
    assert "ceiling" in instr.lower()
    assert not _BRANDS.search(instr)


def test_subagent_prompt_tells_it_to_check_the_ceiling():
    brief = {
        "matched": True, "active_profile": "p", "signature": "s", "expected_ok": True,
        "displays": [{"index": 0, "width": 100, "height": 100, "is_main": True,
                      "origin_x": 0, "origin_y": 0, "dpi": 96}],
    }
    p = pilot_brief(brief, "read the total")["subagent_prompt"]
    assert "main_ceiling" in p
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_delegation.py -q`
Expected: FAIL — `main_ceiling` absent from instructions and prompt.

- [ ] **Step 3: Implement**

```python
# src/daimon/senses/delegation.py — extend build_server_instructions() to append a ceiling note.
# Add a small helper and include it:
def hands_ceiling_note() -> str:
    """Agnostic note: know your authorization envelope before acting."""
    return (
        "## Hands authorization ceiling\n"
        "Daimon enforces a Hands ceiling (L0–L4). Call main_ceiling before driving to learn the "
        "active ceiling and which tools are above it (gated_above). An action above the ceiling is "
        "refused — declare up-front that you cannot do it rather than attempting and being refused "
        "mid-flow. You never raise the ceiling; only the human does."
    )
```

```python
# src/daimon/senses/delegation.py — in build_server_instructions(), append it:
def build_server_instructions() -> str:
    return (
        "Daimon is a local perception + action organ for any AI client: see the screen "
        "(vue_*), read the accessibility tree (touche_*), act with the Hands (main_*), and "
        "show overlays (overlay_*). It is pull-only and calls no AI itself.\n\n"
        + delegation_protocol_text()
        + "\n\n"
        + hands_ceiling_note()
    )
```

```python
# src/daimon/senses/delegation.py — in _subagent_prompt(), add a ceiling step. Insert this line
# into the "How to act:" block (before the perceive line):
        "- First call main_ceiling to learn your authorization envelope; do not attempt actions "
        "listed in gated_above — report them as out of scope instead.\n"
```

- [ ] **Step 4: Run tests + full suite**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_delegation.py -q && /Users/Ben/.hfenv/bin/pytest -q`
Expected: PASS, full suite green.

- [ ] **Step 5: Commit**

```bash
git add src/daimon/senses/delegation.py tests/test_delegation.py
git commit -m "feat(delegation): surface the Hands ceiling so the AI declares above-ceiling acts up-front

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: ③ `ConsentManager.engage_confirmed` (tray engagement path)

**Files:**
- Modify: `src/daimon/motor/consent.py`
- Test: `tests/test_motor_consent.py`

**Interfaces:**
- Consumes: `AppendOnlyLedger` (existing), `Level` (existing).
- Produces: `ConsentManager.engage_confirmed(*, ts: str, source: str = "tray") -> bool` — engages L4 without a typed phrase (the human's confirmed popup is the deliberate gesture). Writes ledger event `{"event":"engage_l4","ts":ts,"method":"confirmed","source":source}` and the engaged state file. Returns True.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_motor_consent.py — add (mirror the existing tests' construction of a ConsentManager)
def test_engage_confirmed_raises_ceiling_and_is_ledgered(tmp_path):
    from daimon.motor.audit import AppendOnlyLedger
    from daimon.motor.consent import ConsentManager
    from daimon.motor.types import Level

    ledger = AppendOnlyLedger(tmp_path / "consent.jsonl")
    state = tmp_path / "state.json"
    cm = ConsentManager(Level.VALIDATION, "I ENGAGE", "I DISENGAGE", ledger, state)

    assert cm.current_ceiling() == Level.VALIDATION
    assert cm.engage_confirmed(ts="2026-06-20T10:00:00Z") is True
    assert cm.current_ceiling() == Level.AUTONOMOUS
    last = ledger._records()[-1]
    assert last["event"] == "engage_l4" and last["method"] == "confirmed"
    # disengage still works and drops back to config
    assert cm.disengage("I DISENGAGE", ts="2026-06-20T10:05:00Z") is True
    assert cm.current_ceiling() == Level.VALIDATION


def test_engaged_state_without_ledger_event_does_not_grant_l4(tmp_path):
    # Anti-forge: a state file flipped to engaged but no engage_l4 ledger event = still config.
    from daimon.motor.audit import AppendOnlyLedger
    from daimon.motor.consent import ConsentManager
    from daimon.motor.types import Level
    import json

    ledger = AppendOnlyLedger(tmp_path / "consent.jsonl")
    state = tmp_path / "state.json"
    state.write_text(json.dumps({"engaged": True, "ts": "x"}), encoding="utf-8")
    cm = ConsentManager(Level.VALIDATION, "E", "D", ledger, state)
    assert cm.current_ceiling() == Level.VALIDATION
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_motor_consent.py -q`
Expected: FAIL — `AttributeError: 'ConsentManager' object has no attribute 'engage_confirmed'`.

- [ ] **Step 3: Implement**

```python
# src/daimon/motor/consent.py — add a method on ConsentManager
    def engage_confirmed(self, *, ts: str, source: str = "tray") -> bool:
        """Engage L4 from a human-confirmed UI gesture (no typed phrase).

        The deliberate consent gesture is the confirmation popup shown out-of-band by the tray;
        the engagement is still recorded immutably in the ledger and is reversible via disengage().
        """
        self._ledger.append({"event": "engage_l4", "ts": ts, "method": "confirmed", "source": source})
        self._state_path.write_text(json.dumps({"engaged": True, "ts": ts}), encoding="utf-8")
        return True
```

- [ ] **Step 4: Run test to verify it passes + full suite**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_motor_consent.py -q && /Users/Ben/.hfenv/bin/pytest -q`
Expected: PASS, full suite green.

- [ ] **Step 5: Commit**

```bash
git add src/daimon/motor/consent.py tests/test_motor_consent.py
git commit -m "feat(motor): consent.engage_confirmed — ledgered L4 engagement from a confirmed UI gesture

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: ③ Tray menu L4 engage/disengage entries

**Files:**
- Modify: `src/daimon/tray/menu_model.py`
- Test: `tests/test_tray_menu.py`

**Interfaces:**
- Consumes: `TrayState` (has `.l4_active`, `.ceiling`, `.clients`, …).
- Produces: menu entries with `action_id="engage_l4"` (when not active) / `action_id="disengage_l4"` (when active). The L0–L3 ceiling radios are unchanged.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_tray_menu.py — add (reuse the file's TrayState construction helper if present;
# otherwise build a minimal state the same way build_menu expects)
from daimon.tray.menu_model import build_menu


def _action_ids(items):
    out = []
    for it in items:
        out.append(it.action_id)
        out.extend(_action_ids(it.children))
    return out


def test_menu_offers_engage_l4_when_inactive(make_state):
    items = build_menu(make_state(l4_active=False))
    ids = _action_ids(items)
    assert "engage_l4" in ids and "disengage_l4" not in ids


def test_menu_offers_disengage_l4_when_active(make_state):
    items = build_menu(make_state(l4_active=True))
    ids = _action_ids(items)
    assert "disengage_l4" in ids and "engage_l4" not in ids


def test_ceiling_radios_stay_l0_to_l3(make_state):
    ids = _action_ids(build_menu(make_state(l4_active=False)))
    assert "set_ceiling:AUTONOMOUS" not in ids
    assert "set_ceiling:VALIDATION" in ids
```

If `tests/test_tray_menu.py` has no `make_state` fixture, add one at the top of the file built from the real `TrayState` (read `src/daimon/tray/state.py` for its fields) — e.g.:

```python
import pytest
from daimon.tray.state import TrayState
from daimon.motor.types import Level

@pytest.fixture
def make_state():
    def _make(**over):
        base = dict(version="0.0.0", screen_ok=True, accessibility_ok=True, clients=(),
                    ceiling=Level.VALIDATION, overlay_on=False, l4_active=False)
        base.update(over)
        return TrayState(**base)
    return _make
```

(Match the real `TrayState` field names; adjust the `base` dict to whatever `TrayState` actually requires.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_tray_menu.py -q`
Expected: FAIL — no `engage_l4`/`disengage_l4` action ids.

- [ ] **Step 3: Implement**

```python
# src/daimon/tray/menu_model.py — replace the existing l4_active block:
#   if state.l4_active:
#       items.append(MenuItem(kind="label", label="⚠️ L4 AUTONOMY ACTIVE", enabled=False))
# with the label PLUS an engage/disengage action:
    if state.l4_active:
        items.append(MenuItem(kind="label", label="⚠️ L4 AUTONOMY ACTIVE", enabled=False))
        items.append(MenuItem(kind="action", label="Disengage L4 autonomy",
                              action_id="disengage_l4"))
    else:
        items.append(MenuItem(kind="action", label="Engage L4 autonomy…",
                              action_id="engage_l4"))
```

(The L0–L3 ceiling radios come from `_SETTABLE_CEILINGS`, which already excludes AUTONOMOUS — leave it unchanged. Update its comment to note L4 is now reached via the engage action, not a radio.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_tray_menu.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/daimon/tray/menu_model.py tests/test_tray_menu.py
git commit -m "feat(tray): L4 engage/disengage menu entries (radios stay L0-L3)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: ③ Tray AppKit — NSAlert disclaimer wired to consent

**Files:**
- Modify: `src/daimon/tray/app/statusitem.py` (`_dispatch`)
- Manual validation only (AppKit; no unit test — follows the repo's "GUI thin, smoke" pattern)

**Interfaces:**
- Consumes: `engage_l4`/`disengage_l4` action ids (Task 6), `ConsentManager.engage_confirmed`/`disengage` (Task 5), `build_consent()` (`motor/factory.py`).

- [ ] **Step 1: Implement the dispatch branches**

```python
# src/daimon/tray/app/statusitem.py — inside _dispatch(self, action_id), add two branches
# alongside the existing ones (e.g. after the "set_ceiling:" branch). Use the project's
# timestamp helper if one exists; otherwise datetime.now(timezone.utc).isoformat().
        elif action_id == "engage_l4":
            try:
                from AppKit import NSAlert, NSAlertFirstButtonReturn
                alert = NSAlert.alloc().init()
                alert.setMessageText_("Engage L4 autonomy?")
                alert.setInformativeText_(
                    "This removes ALL per-action validation. Every action the AI requests will "
                    "execute immediately, recorded in the immutable consent ledger. You can "
                    "disengage anytime from this menu."
                )
                alert.addButtonWithTitle_("Engage")
                alert.addButtonWithTitle_("Cancel")
                if alert.runModal() == NSAlertFirstButtonReturn:
                    from datetime import datetime, timezone
                    from ...motor.factory import build_consent
                    build_consent().engage_confirmed(
                        ts=datetime.now(timezone.utc).isoformat(), source="tray")
                    self._refresh()
            except Exception:
                log_exception(action_id)

        elif action_id == "disengage_l4":
            try:
                from datetime import datetime, timezone
                from ...motor.factory import build_consent
                # Disengage uses the configured phrase path; the tray passes it directly since the
                # human already chose "disengage" from the menu.
                cm = build_consent()
                cm.disengage(cm._disengagement_phrase, ts=datetime.now(timezone.utc).isoformat())
                self._refresh()
            except Exception:
                log_exception(action_id)
```

Notes for the implementer:
- Match the existing `_dispatch` style (how other branches import + call `self._refresh()` or the real refresh method name — read the surrounding branches).
- `disengage()` requires the exact disengagement phrase. Reading `cm._disengagement_phrase` is acceptable here because the human's menu choice IS the gesture; if `build_consent()` exposes the phrase differently, use that. (If preferred, add a thin `ConsentManager.disengage_confirmed(*, ts)` mirroring Task 5 — but only if `disengage` can't be called cleanly.)

- [ ] **Step 2: Smoke-validate the dispatch imports**

Run: `/Users/Ben/.hfenv/bin/python -c "import ast; ast.parse(open('src/daimon/tray/app/statusitem.py').read()); print('parse ok')"`
Expected: `parse ok` (AppKit modal can't run headless; full validation is manual on Ben's Mac).

- [ ] **Step 3: Run the full suite (no regression)**

Run: `/Users/Ben/.hfenv/bin/pytest -q`
Expected: PASS (count unchanged from Task 6 — this task adds no unit tests).

- [ ] **Step 4: Commit**

```bash
git add src/daimon/tray/app/statusitem.py
git commit -m "feat(tray): NSAlert L4 engage/disengage wired to the consent ledger

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Final verification

- [ ] Full suite green: `/Users/Ben/.hfenv/bin/pytest -q` (> 374).
- [ ] `grep -rn "print(" src/daimon/server.py src/daimon/senses/delegation.py` shows no startup print added.
- [ ] Server-instructions stay agnostic: `grep -riE "haiku|claude|gpt|gemini|opus|sonnet|llama|mistral" src/daimon/senses/delegation.py` → empty.
- [ ] `git status` clean; 7 commits on main.

## Field validation (post-merge, for Ben — not blocking)

- At L3: `main_key(cmd+M)` and typing execute without a gate; a destructive combo still gates; clicking an unverified target still gates.
- `main_ceiling` returns the right envelope; a delegated sub-agent calls it and skips gated_above tools.
- Tray "Engage L4 autonomy…" shows the disclaimer, engages on confirm, the menu flips to "Disengage", a full delegated drive runs with no prompts, and disengage drops back — both events present in `logs/consent.jsonl`.

## Out of scope (YAGNI)

- Graded gating beyond the keyboard fix; `main_window_minimize/hide` AX primitives; `focus_warning` refinement — all AXE 4b.
- Delegation prompt robustness (Step-0 ToolSearch / anti-abandon / agnostic capability reframe) — stream B.
- Including the full ceiling_report inside vue_pilot_brief's packet (the sub-agent calls main_ceiling instead — avoids coupling Vue to motor consent).
