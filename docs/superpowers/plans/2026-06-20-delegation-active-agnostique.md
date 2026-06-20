# AXE 5b — Active LLM-Agnostic Delegation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Daimon's delegation contract active and LLM-agnostic by surfacing it through the MCP protocol itself (server-instructions + a `vue_pilot_brief` tool), so any orchestrator that can spawn sub-agents delegates UI-driving to its smallest capable model — while Daimon still calls no AI.

**Architecture:** A new pure core module `senses/delegation.py` holds the agnostic protocol text and the per-task brief builder (no OS, no LLM). Two thin surfaces consume it: `server.py` passes the composed instructions to `FastMCP`, and `senses/vue.py` adds a `vue_pilot_brief` tool that joins the existing AXE 2 profile gate with the brief builder.

**Tech Stack:** Python 3.12, FastMCP (`mcp.server.fastmcp`), pytest. No new runtime dependency.

## Global Constraints

- Run the suite with: `/Users/Ben/.hfenv/bin/pytest -q` — must stay green (currently 363 passing) and grow.
- **Daimon calls no AI** — no model dependency, no driver loop. Pull doctrine intact.
- **Agnostic** — no model/brand name in any produced text (`Haiku|Claude|GPT|Gemini|Opus|Sonnet|Llama|Mistral`, case-insensitive). Asserted by test.
- **No `print` at import/startup** — MCP stdio must stay intact.
- Security text in the contract must restate: L0–L4 Hands ceiling + secret redaction are enforced by Daimon; the sub-agent never raises the ceiling.
- Conventional commits; end body with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: Agnostic delegation protocol text

**Files:**
- Create: `src/daimon/senses/delegation.py`
- Test: `tests/test_delegation.py`

**Interfaces:**
- Produces: `delegation_protocol_text() -> str`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_delegation.py
import re
from daimon.senses.delegation import delegation_protocol_text

_BRANDS = re.compile(r"haiku|claude|gpt|gemini|opus|sonnet|llama|mistral", re.I)


def test_protocol_text_is_agnostic_and_tiered():
    txt = delegation_protocol_text()
    assert txt.strip()
    assert not _BRANDS.search(txt), "protocol must name no model/brand"
    low = txt.lower()
    assert "vue_pilot_brief" in low
    assert "sub-agent" in low or "subagent" in low      # tier 1: delegate
    assert "inline" in low                               # tier 2: run inline
    assert "vue_calibrate" in low                        # go/no-go fallback
    assert "space='image'" in txt or 'space="image"' in txt
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_delegation.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'daimon.senses.delegation'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/daimon/senses/delegation.py
"""Agnostic, AI-free delegation contract surfaced through the MCP protocol (AXE 5b).

Daimon never calls an LLM. It only describes — in model-agnostic terms — how an
orchestrator should hand a UI-driving task to a cheaper/faster sub-agent (or run it
inline if it cannot spawn one). The text here is injected into the MCP
server-instructions; the per-task packet is built by pilot_brief().
"""

from __future__ import annotations


def delegation_protocol_text() -> str:
    """The agnostic delegation section injected into the MCP server-instructions."""
    return (
        "## Delegating UI-driving tasks\n"
        "For multi-step tasks that drive an on-screen UI and extract text, first call "
        "vue_pilot_brief(objective, expected=<profile name if known>) to get a go/no-go "
        "gate plus a ready-to-paste sub-agent prompt.\n"
        "- If you can spawn sub-agents: run the returned subagent_prompt on the smallest, "
        "fastest model you have that can reliably click and read; keep its screenshots inside "
        "the sub-agent and bubble up only the extracted text.\n"
        "- If you cannot spawn sub-agents: run the same prompt inline with your current model.\n"
        "Always drive with space='image' + display=k (Daimon resolves pixels itself — never "
        "reason about coordinates); Daimon enforces the L0-L4 Hands ceiling and secret redaction "
        "regardless. If the gate is not ready, calibrate first (vue_calibrate); do not drive blind."
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_delegation.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/daimon/senses/delegation.py tests/test_delegation.py
git commit -m "feat(delegation): agnostic delegation protocol text (AXE 5b)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Per-task brief builder `pilot_brief`

**Files:**
- Modify: `src/daimon/senses/delegation.py`
- Test: `tests/test_delegation.py`

**Interfaces:**
- Consumes: a `profile_brief` dict shaped like `active_profile_brief()` output —
  `{matched: bool, active_profile: str|None, signature: str, expected_ok: bool, displays: [{index, width, height, is_main, origin_x, origin_y, dpi}]}`.
- Produces: `pilot_brief(profile_brief: dict, objective: str) -> dict` returning
  `{gate, ready: bool, contract:{input, output, rules}, subagent_prompt: str, mode_hint: str, next: str}`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_delegation.py
import re as _re
import pytest
from daimon.senses.delegation import pilot_brief

_READY_BRIEF = {
    "matched": True, "active_profile": "bureau-3-ecrans", "signature": "abc",
    "expected_ok": True,
    "displays": [
        {"index": 0, "width": 1512, "height": 982, "is_main": True, "origin_x": 0, "origin_y": 0, "dpi": 255},
        {"index": 1, "width": 1600, "height": 900, "is_main": False, "origin_x": 1512, "origin_y": 34, "dpi": 239},
    ],
}
_UNMATCHED_BRIEF = {"matched": False, "active_profile": None, "signature": "z",
                    "expected_ok": False, "displays": []}
_MISMATCH_BRIEF = {**_READY_BRIEF, "expected_ok": False}


def test_pilot_brief_ready_builds_coord_free_prompt():
    out = pilot_brief(_READY_BRIEF, "open the invoice and read the total")
    assert out["ready"] is True
    assert out["mode_hint"] == "delegate_to_smallest_capable_subagent_else_run_inline"
    p = out["subagent_prompt"]
    assert "open the invoice and read the total" in p
    assert "display=0" in p and "display=1" in p
    assert not _re.search(r"\d+\s*,\s*\d+", p), "prompt must carry no coordinate pairs"
    assert _BRANDS.search(p) is None
    joined = " ".join(out["contract"]["rules"]).lower()
    assert "ceiling" in joined and "secret" in joined


def test_pilot_brief_not_ready_when_unmatched():
    out = pilot_brief(_UNMATCHED_BRIEF, "do X")
    assert out["ready"] is False
    assert out["subagent_prompt"] == ""
    assert "vue_calibrate" in out["next"]


def test_pilot_brief_not_ready_on_expected_mismatch():
    out = pilot_brief(_MISMATCH_BRIEF, "do X")
    assert out["ready"] is False
    assert "vue_calibrate" in out["next"]


def test_pilot_brief_rejects_empty_objective():
    with pytest.raises(ValueError):
        pilot_brief(_READY_BRIEF, "   ")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_delegation.py -q`
Expected: FAIL with `ImportError: cannot import name 'pilot_brief'`

- [ ] **Step 3: Write minimal implementation**

```python
# append to src/daimon/senses/delegation.py

_RULES = [
    "Use space='image' + display=k from the brief; never reason about pixel geometry.",
    "Keep screenshots in your own context; return only the extracted text.",
    "Daimon enforces the L0-L4 Hands ceiling and secret redaction; never try to raise the ceiling.",
]

_MODE_HINT = "delegate_to_smallest_capable_subagent_else_run_inline"


def _subagent_prompt(profile: str, indices: list[int], objective: str) -> str:
    addr = ", ".join(f"display={i}" for i in indices)
    return (
        f"You are driving a UI through the Daimon MCP tools. Active calibration profile: "
        f"'{profile}'. Addressable displays: {addr}.\n"
        f"Objective: {objective}\n"
        "How to act:\n"
        "- Perceive with vue_snapshot(display=k) and read the labels. For apps with no "
        "accessibility tree, call vue_find(text=...) to get a clickable target.\n"
        "- Act with main_click/main_type using space='image' and the display index; Daimon "
        "resolves pixels to global itself. Never compute or pass raw global coordinates.\n"
        "- " + "\n- ".join(_RULES) + "\n"
        "Return ONLY the text you were asked to extract, nothing else."
    )


def pilot_brief(profile_brief: dict, objective: str) -> dict:
    """Build the per-task delegation packet from an active_profile_brief() result."""
    objective = (objective or "").strip()
    if not objective:
        raise ValueError("pilot_brief needs a non-empty objective")
    matched = bool(profile_brief.get("matched"))
    expected_ok = bool(profile_brief.get("expected_ok"))
    ready = matched and expected_ok
    displays = profile_brief.get("displays") or []
    profile_name = profile_brief.get("active_profile")
    gate = {
        "matched": matched,
        "active_profile": profile_name,
        "expected_ok": expected_ok,
        "displays": displays,
    }
    contract = {
        "input": {"profile": profile_name, "objective": objective},
        "output": "extracted text only",
        "rules": list(_RULES),
    }
    if not ready:
        return {
            "gate": gate, "ready": False, "contract": contract,
            "subagent_prompt": "", "mode_hint": _MODE_HINT,
            "next": ("Environment does not match the expected profile. Call "
                     "vue_calibrate(name=...) to register/select the right profile first; "
                     "do not drive blind."),
        }
    indices = [d["index"] for d in displays]
    return {
        "gate": gate, "ready": True, "contract": contract,
        "subagent_prompt": _subagent_prompt(profile_name, indices, objective),
        "mode_hint": _MODE_HINT,
        "next": ("Ready. If you can spawn a sub-agent, run subagent_prompt on the smallest "
                 "capable model; otherwise run it inline."),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_delegation.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/daimon/senses/delegation.py tests/test_delegation.py
git commit -m "feat(delegation): per-task pilot_brief packet builder (AXE 5b)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Server-instructions builder + wire into FastMCP

**Files:**
- Modify: `src/daimon/senses/delegation.py`
- Modify: `src/daimon/server.py:306` (the `mcp = FastMCP("daimon")` line)
- Test: `tests/test_delegation.py`, `tests/test_server_tools.py`

**Interfaces:**
- Consumes: `delegation_protocol_text()` (Task 1).
- Produces: `build_server_instructions() -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_delegation.py
from daimon.senses.delegation import build_server_instructions


def test_server_instructions_carry_the_protocol():
    instr = build_server_instructions()
    assert "Daimon" in instr
    assert "vue_pilot_brief" in instr               # the delegation protocol is included
    assert not _BRANDS.search(instr)
```

```python
# append to tests/test_server_tools.py
from daimon.server import build_server


def test_server_advertises_delegation_in_instructions():
    instr = getattr(build_server(), "instructions", "") or ""
    assert "vue_pilot_brief" in instr
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_delegation.py tests/test_server_tools.py -q`
Expected: FAIL — `ImportError: cannot import name 'build_server_instructions'` and the server test asserts an instruction string that isn't set yet.

- [ ] **Step 3: Write minimal implementation**

```python
# append to src/daimon/senses/delegation.py

def build_server_instructions() -> str:
    """The MCP server-instructions Daimon advertises to every client at connect."""
    return (
        "Daimon is a local perception + action organ for any AI client: see the screen "
        "(vue_*), read the accessibility tree (touche_*), act with the Hands (main_*), and "
        "show overlays (overlay_*). It is pull-only and calls no AI itself.\n\n"
        + delegation_protocol_text()
    )
```

```python
# src/daimon/server.py — change the FastMCP construction line
# at top of file, with the other senses imports:
from .senses.delegation import build_server_instructions
# at line ~306:
    mcp = FastMCP("daimon", instructions=build_server_instructions())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_delegation.py tests/test_server_tools.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/daimon/senses/delegation.py src/daimon/server.py tests/test_delegation.py tests/test_server_tools.py
git commit -m "feat(server): advertise agnostic delegation in MCP instructions (AXE 5b)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `vue_pilot_brief` MCP tool

**Files:**
- Modify: `src/daimon/senses/vue.py` (import `pilot_brief`; register the tool next to `vue_profile_brief` at ~line 255-271)
- Test: `tests/test_server_tools.py`

**Interfaces:**
- Consumes: `active_profile_brief(self._profiles, displays, expected)` (already imported in vue.py) and `pilot_brief` (Task 2); `screen.list_displays()` (already used by `vue_profile_brief`).
- Produces: MCP tool `vue_pilot_brief(objective: str, expected: str | None = None) -> dict`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_server_tools.py
def test_vue_pilot_brief_is_registered():
    import asyncio
    names = {t.name for t in asyncio.run(build_server().list_tools())}
    assert "vue_pilot_brief" in names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_server_tools.py::test_vue_pilot_brief_is_registered -q`
Expected: FAIL — `vue_pilot_brief` not in the tool set.

- [ ] **Step 3: Write minimal implementation**

```python
# src/daimon/senses/vue.py — extend the existing import from .calibration
from .calibration import (
    active_profile_brief,
    # ...existing names...
)
from .delegation import pilot_brief
```

```python
# src/daimon/senses/vue.py — register right after the vue_profile_brief tool (~line 271)
        @mcp.tool(
            name="vue_pilot_brief",
            description=(
                "Per-task delegation packet for a UI-driving/extraction task. Returns the "
                "active-profile go/no-go gate plus a ready-to-paste sub-agent prompt. Call this "
                "BEFORE driving the UI: if you can spawn sub-agents, run subagent_prompt on your "
                "smallest capable model and keep its screenshots out of your context; otherwise "
                "run it inline. Returns {gate, ready, contract, subagent_prompt, mode_hint, next}. "
                "If ready is False, the live screen doesn't match the expected profile — calibrate "
                "first, don't drive blind."
            ),
        )
        def vue_pilot_brief(objective: str, expected: str | None = None) -> dict:
            displays = screen.list_displays()
            brief = active_profile_brief(self._profiles, displays, expected=expected)
            return pilot_brief(brief, objective)
```

(If the `.calibration` import is a single-line `from .calibration import active_profile_brief, ...`, just add `pilot_brief` via the separate `from .delegation import pilot_brief` line shown above — do not merge modules.)

- [ ] **Step 4: Run the test to verify it passes**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_server_tools.py::test_vue_pilot_brief_is_registered -q`
Expected: PASS

- [ ] **Step 5: Run the full suite + commit**

Run: `/Users/Ben/.hfenv/bin/pytest -q`
Expected: PASS (all green, count > 363)

```bash
git add src/daimon/senses/vue.py tests/test_server_tools.py
git commit -m "feat(vue): vue_pilot_brief delegation tool (AXE 5b)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Generalize the delegation recipe doc (agnostic)

**Files:**
- Rename: `docs/delegation-haiku-via-profil.md` → `docs/delegation-via-profil.md`
- Modify: the renamed doc

**Interfaces:** none (documentation only).

- [ ] **Step 1: Rename the file**

```bash
git mv docs/delegation-haiku-via-profil.md docs/delegation-via-profil.md
```

- [ ] **Step 2: Make the content agnostic + point at the active mechanism**

Edit `docs/delegation-via-profil.md`:
- Replace every model-specific mention (the title and body say "Haiku") with "le plus petit modèle capable de ton runtime" / "a small fast capable model". Title becomes: `# Déléguer le pilotage Daimon à un petit modèle via profil (AXE 5/5b)`.
- Add, near the top, a short "Mécanisme actif" note: the contract is now surfaced live by Daimon itself — the MCP **server-instructions** carry the delegation protocol, and the **`vue_pilot_brief(objective, expected?)`** tool returns the per-task gate + ready-to-paste sub-agent prompt. This doc is the human reference; `vue_pilot_brief` is the machine source of truth.
- Keep the two capability tiers explicit: can spawn sub-agents → delegate to the smallest capable model; cannot → run inline with the loaded model.

- [ ] **Step 3: Verify no brand name remains**

Run: `grep -riE 'haiku|claude|gpt|gemini|opus|sonnet|llama|mistral' docs/delegation-via-profil.md`
Expected: no output (empty).

- [ ] **Step 4: Commit**

```bash
git add docs/delegation-via-profil.md
git commit -m "docs(delegation): generalize recipe to be LLM-agnostic + point at active mechanism (AXE 5b)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Final verification

- [ ] Run the full suite: `/Users/Ben/.hfenv/bin/pytest -q` → all green, count > 363.
- [ ] `grep -rn "print(" src/daimon/server.py` shows no startup print added.
- [ ] `git status` clean; 5 commits on main.

## Out of scope (YAGNI)

- No client-capability detection (the orchestrator self-knows).
- No model-selection logic inside Daimon.
- No new config.
- No internal driver/loop (would break the "Daimon calls no AI" invariant).

## Field validation (post-merge, for Ben — not blocking)

- In a real MCP client: confirm an orchestrator that can spawn sub-agents actually delegates via `vue_pilot_brief`, and the sub-agent's screenshots stay out of the orchestrator context (only text bubbles up).
