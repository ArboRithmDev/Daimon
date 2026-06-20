# AXE 4b — Native Window Control + Must-Delegate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the Hands deterministic window primitives (minimize/hide/show via AX + NSRunningApplication, immune to app keybindings), make `main_click` auto-focus by default, refine the focus result to three states, and make the delegation protocol require a capable model to delegate multi-step driving.

**Architecture:** New L1 NONDESTRUCTIVE motor actions `window_minimize/hide/show` flow through the existing organ→guard→actuator chain. The macOS actuator resolves the app the same way `_activate` does (NSWorkspace) and acts via `NSRunningApplication.hide/unhide` + AX `kAXMinimizedAttribute`. Server tools, the ensure_focus default, the focus-state refinement, and the delegation imperative are thin additions.

**Tech Stack:** Python 3.12, pyobjc (AppKit/ApplicationServices), FastMCP, pytest.

## Global Constraints

- Run the suite with: `/Users/Ben/.hfenv/bin/pytest -q` — must stay green (currently 393) and grow.
- Window ops are **L1 NONDESTRUCTIVE**, reversible, and flow through `organ.act` → guard (refused under L0). They carry no screen target → `requires_observed_target=False`.
- The guard stays the single chokepoint; no new ceiling level; no secret path touched.
- **Do NOT create `src/daimon/motor/actuator_win.py`** — `feat/windows-port` already has a real one; Windows parity is a TODO in the macOS method docstrings (`ShowWindow SW_MINIMIZE/SW_HIDE/SW_RESTORE`), added to the existing `WindowsActuator` at merge.
- `MotorAction.name` is the SHORT verb (`window_hide`); tool name is `main_` + name.
- No `print` at import/startup. Delegation text stays agnostic (no model/brand name; the `_BRANDS` regex test guards it).
- Conventional commits; end body with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.

---

### Task 1: Window action definitions

**Files:**
- Modify: `src/daimon/motor/actions.py`
- Test: `tests/test_motor_actions.py`

**Interfaces:**
- Produces: `ACTIONS` entries `main_window_minimize`, `main_window_hide`, `main_window_show` (Level.NONDESTRUCTIVE, `requires_observed_target=False`). Their MotorAction short names: `window_minimize`, `window_hide`, `window_show`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_motor_actions.py — add
from daimon.motor.actions import ACTIONS, level_for, requires_observed_target, ceiling_report
from daimon.motor.types import Level


def test_window_ops_are_nondestructive_and_targetless():
    for tool in ("main_window_minimize", "main_window_hide", "main_window_show"):
        assert tool in ACTIONS
        assert level_for(tool) == Level.NONDESTRUCTIVE
    # SHORT verb form is what the guard/actuator see; observation not required.
    for verb in ("window_minimize", "window_hide", "window_show"):
        assert requires_observed_target(verb) is False
    # exposed in the ceiling report's level map
    assert ceiling_report(Level.VALIDATION)["levels"]["main_window_hide"] == "NONDESTRUCTIVE"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_motor_actions.py::test_window_ops_are_nondestructive_and_targetless -q`
Expected: FAIL — `main_window_minimize` not in ACTIONS.

- [ ] **Step 3: Implement**

```python
# src/daimon/motor/actions.py — add these three entries to the ACTIONS dict
    "main_window_minimize": ActionDef("main_window_minimize", Level.NONDESTRUCTIVE,
                                      "minimize the target window", requires_observed_target=False),
    "main_window_hide": ActionDef("main_window_hide", Level.NONDESTRUCTIVE,
                                  "hide the target app", requires_observed_target=False),
    "main_window_show": ActionDef("main_window_show", Level.NONDESTRUCTIVE,
                                  "unhide + un-minimize + raise the target app", requires_observed_target=False),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_motor_actions.py::test_window_ops_are_nondestructive_and_targetless -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/daimon/motor/actions.py tests/test_motor_actions.py
git commit -m "feat(motor): window_minimize/hide/show action defs (L1, targetless)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: macOS actuator window backend

**Files:**
- Modify: `src/daimon/motor/actuator.py` (MacOSActuator: extract the handler map, add three methods)
- Test: `tests/test_motor_actuator.py`

**Interfaces:**
- Consumes: `MotorAction` with `name` in `{window_minimize, window_hide, window_show}` and `params` containing `bundle`/`title`/`pid`.
- Produces: `MacOSActuator` handles those three names (dispatch); `MacOSActuator._handlers() -> dict` exposes the name→method map for introspection. `FakeActuator` already records any action by name (unchanged).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_motor_actuator.py — add (mirror how this file builds a MotorAction)
from daimon.motor.actuator import MacOSActuator, FakeActuator
from daimon.motor.types import MotorAction, Target


def test_macos_actuator_dispatches_window_ops():
    handlers = MacOSActuator()._handlers()
    for verb in ("window_minimize", "window_hide", "window_show"):
        assert verb in handlers


def test_fake_actuator_records_window_op():
    fake = FakeActuator()
    a = MotorAction(name="window_hide", level=None, target=Target(), params={"bundle": "com.x"})
    r = fake.execute(a)
    assert r == {"status": "executed", "action": "window_hide"}
    assert fake.executed[-1].name == "window_hide"
```

(If `MotorAction` requires a non-None `level`/`declaration`, read `tests/test_motor_actuator.py` and match how it constructs actions — the test's intent is "the fake records the window op; the real actuator's dispatch knows it".)

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_motor_actuator.py -q -k window`
Expected: FAIL — `MacOSActuator` has no `_handlers`, window verbs unknown.

- [ ] **Step 3: Implement**

Extract the dispatch dict from `execute()` into `_handlers()`, then add the three handlers.

```python
# src/daimon/motor/actuator.py — in MacOSActuator, replace the inline dict in execute()
    def _handlers(self):
        return {
            "click": self._click, "type": self._type, "drag": self._drag,
            "press": self._press, "navigate": self._navigate, "key": self._key,
            "hover": self._hover, "activate": self._activate,
            "mouse_down": self._mouse_down, "mouse_up": self._mouse_up,
            "key_down": self._key_down, "key_up": self._key_up,
            "window_minimize": self._window_minimize,
            "window_hide": self._window_hide,
            "window_show": self._window_show,
        }

    def execute(self, action: MotorAction) -> dict:
        """Dispatch the action to its handler after ticking the hold watchdog."""
        self._watchdog.tick()
        handler = self._handlers().get(action.name)
        if handler is None:
            raise ValueError(f"unknown action: {action.name}")
        handler(action)
        return {"status": "executed", "action": action.name}
```

```python
# src/daimon/motor/actuator.py — add three methods on MacOSActuator.
# Windows parity (do NOT create actuator_win.py here): the WindowsActuator on
# feat/windows-port gets these via ShowWindow SW_MINIMIZE / SW_HIDE / SW_RESTORE.
    def _running_app(self, p: dict):
        from AppKit import NSWorkspace
        for app in NSWorkspace.sharedWorkspace().runningApplications():
            if (p.get("bundle") and app.bundleIdentifier() == p["bundle"]) or \
               (p.get("title") and app.localizedName() == p["title"]) or \
               (p.get("pid") and int(app.processIdentifier()) == p["pid"]):
                return app
        raise RuntimeError(f"No app matching {p}")

    def _window_hide(self, action: MotorAction) -> None:
        # Windows twin: ShowWindow(hwnd, SW_HIDE). TODO real Win runtime (actuator_win).
        self._running_app(action.params).hide()

    def _window_minimize(self, action: MotorAction) -> None:
        # Windows twin: ShowWindow(hwnd, SW_MINIMIZE). TODO real Win runtime (actuator_win).
        from ApplicationServices import (
            AXUIElementCreateApplication, AXUIElementCopyAttributeValue,
            AXUIElementSetAttributeValue, kAXFocusedWindowAttribute,
            kAXWindowsAttribute, kAXMinimizedAttribute,
        )
        app = self._running_app(action.params)
        ax = AXUIElementCreateApplication(int(app.processIdentifier()))
        err, win = AXUIElementCopyAttributeValue(ax, kAXFocusedWindowAttribute, None)
        if err != 0 or win is None:
            err, wins = AXUIElementCopyAttributeValue(ax, kAXWindowsAttribute, None)
            if err != 0 or not wins:
                raise RuntimeError("no window to minimize")
            win = wins[0]
        AXUIElementSetAttributeValue(win, kAXMinimizedAttribute, True)

    def _window_show(self, action: MotorAction) -> None:
        # Windows twin: ShowWindow(hwnd, SW_RESTORE). TODO real Win runtime (actuator_win).
        from ApplicationServices import (
            AXUIElementCreateApplication, AXUIElementCopyAttributeValue,
            AXUIElementSetAttributeValue, kAXWindowsAttribute, kAXMinimizedAttribute,
        )
        app = self._running_app(action.params)
        app.unhide()
        ax = AXUIElementCreateApplication(int(app.processIdentifier()))
        err, wins = AXUIElementCopyAttributeValue(ax, kAXWindowsAttribute, None)
        if err == 0 and wins:
            for win in wins:
                AXUIElementSetAttributeValue(win, kAXMinimizedAttribute, False)
        app.activateWithOptions_(1 << 1)  # NSApplicationActivateIgnoringOtherApps
```

- [ ] **Step 4: Run tests + full suite**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_motor_actuator.py -q -k window && /Users/Ben/.hfenv/bin/pytest -q`
Expected: PASS, full suite green. (The AX/AppKit bodies are exercised only on a real Mac — manual validation; the tests cover dispatch + the fake.)

- [ ] **Step 5: Commit**

```bash
git add src/daimon/motor/actuator.py tests/test_motor_actuator.py
git commit -m "feat(motor): macOS window minimize/hide/show via AX + NSRunningApplication

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Window MCP tools

**Files:**
- Modify: `src/daimon/server.py` (`_register_motor`, where `organ` is in scope)
- Test: `tests/test_server_tools.py`

**Interfaces:**
- Consumes: `organ.act`, `level_for` (already imported), `MotorAction`/`Target`/`Declaration` (already imported).
- Produces: MCP tools `main_window_minimize`, `main_window_hide`, `main_window_show` (each `(intent: str, bundle: str = "", title: str = "", pid: int = 0) -> dict`).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server_tools.py — add
def test_window_tools_are_registered():
    import asyncio
    names = {t.name for t in asyncio.run(build_server().list_tools())}
    assert {"main_window_minimize", "main_window_hide", "main_window_show"} <= names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_server_tools.py::test_window_tools_are_registered -q`
Expected: FAIL — the three window tools are not registered.

- [ ] **Step 3: Implement**

```python
# src/daimon/server.py — inside _register_motor, near the other main_* registrations.
# Helper to build the window-targeting params (mirror how params are assembled elsewhere):
    def _window_params(bundle: str, title: str, pid: int) -> dict:
        return {k: v for k, v in (("bundle", bundle), ("title", title), ("pid", pid)) if v}

    def _window_action(verb: str, intent: str, bundle: str, title: str, pid: int) -> dict:
        return organ.act(MotorAction(
            name=verb, level=level_for("main_" + verb), target=Target(),
            declaration=Declaration(reversible=True, intent=intent),
            params=_window_params(bundle, title, pid),
        ))

    @mcp.tool(name="main_window_minimize", description=(
        "Minimize the target app's front window (AX, immune to app key rebinds — unlike a "
        "Cmd+M chord). Target by bundle, title, or pid. Reversible (main_window_show restores)."))
    def main_window_minimize(intent: str, bundle: str = "", title: str = "", pid: int = 0) -> dict:
        return _window_action("window_minimize", intent, bundle, title, pid)

    @mcp.tool(name="main_window_hide", description=(
        "Hide the target app (NSRunningApplication.hide — immune to app key rebinds, unlike "
        "Cmd+H). Target by bundle, title, or pid. Reversible (main_window_show restores)."))
    def main_window_hide(intent: str, bundle: str = "", title: str = "", pid: int = 0) -> dict:
        return _window_action("window_hide", intent, bundle, title, pid)

    @mcp.tool(name="main_window_show", description=(
        "Unhide + un-minimize + raise the target app (restore after minimize/hide). Target by "
        "bundle, title, or pid."))
    def main_window_show(intent: str, bundle: str = "", title: str = "", pid: int = 0) -> dict:
        return _window_action("window_show", intent, bundle, title, pid)
```

- [ ] **Step 4: Run test + full suite**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_server_tools.py::test_window_tools_are_registered -q && /Users/Ben/.hfenv/bin/pytest -q`
Expected: PASS, full suite green.

- [ ] **Step 5: Commit**

```bash
git add src/daimon/server.py tests/test_server_tools.py
git commit -m "feat(server): main_window_minimize/hide/show tools

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `main_click`/`press`/`drag` auto-focus by default

**Files:**
- Modify: `src/daimon/server.py` (three tool signatures)
- Test: `tests/test_server_tools.py` (or wherever the motor tools are tested — read the file first)

**Interfaces:**
- Changes the default of `ensure_focus` from `False` to `True` on `main_click`, `main_press`, `main_drag`. `_attach_focus` already only acts when a window target is given, so no-window calls are unaffected.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server_tools.py — add. Introspect the registered tool's input schema default.
def test_positional_tools_default_to_ensure_focus():
    import asyncio
    tools = {t.name: t for t in asyncio.run(build_server().list_tools())}
    for name in ("main_click", "main_press", "main_drag"):
        schema = tools[name].inputSchema
        assert schema["properties"]["ensure_focus"].get("default") is True, name
```

(If `inputSchema`/`properties` shape differs in this FastMCP version, read how another default-bearing tool is asserted in the suite and match it; the intent is "ensure_focus defaults to True for the three positional tools".)

- [ ] **Step 2: Run test to verify it fails**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_server_tools.py::test_positional_tools_default_to_ensure_focus -q`
Expected: FAIL — default is currently False.

- [ ] **Step 3: Implement**

In `src/daimon/server.py`, change `ensure_focus: bool = False` to `ensure_focus: bool = True` in the signatures of `main_click`, `main_press`, and `main_drag`. Update each tool's description sentence about `ensure_focus` to say it is on by default (e.g. "ensure_focus (on by default) activates a non-frontmost target window before acting").

- [ ] **Step 4: Run test + full suite**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_server_tools.py::test_positional_tools_default_to_ensure_focus -q && /Users/Ben/.hfenv/bin/pytest -q`
Expected: PASS, full suite green (existing focus tests must stay green — they pass window targets explicitly).

- [ ] **Step 5: Commit**

```bash
git add src/daimon/server.py tests/test_server_tools.py
git commit -m "feat(motor): main_click/press/drag auto-focus a non-frontmost target by default

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Three-state focus result

**Files:**
- Modify: `src/daimon/motor/organ.py` (`_handle_focus`)
- Test: `tests/test_motor_focus.py` (or the file that tests `_handle_focus`/focus — read first)

**Interfaces:**
- `_handle_focus` adds a `"focus"` key to its returned dict with one of: `"not_attempted"` (no window target / probe), `"activated_and_frontmost"` (ensure_focus brought it forward), `"activated_but_not_frontmost"` (activated but still not frontmost). Existing keys (`focus_warning`, `focus_detail`, `focused`) are unchanged (additive).

- [ ] **Step 1: Write the failing tests**

Read `src/daimon/motor/organ.py` `_handle_focus` and the existing focus tests to mirror how a MotorAction with a window target + a fake FocusProbe is built. Then add:

```python
# in the focus test file — three cases, using the existing test scaffolding for organ/_handle_focus
def test_focus_state_not_attempted_without_window(...):
    # action with no window target → returned dict has focus == "not_attempted" (or the key absent
    # only when _handle_focus returns {}; assert the documented value for each branch)
    ...

def test_focus_state_activated_and_frontmost(...):
    # ensure_focus=True, fake probe reports the window frontmost after activate → "activated_and_frontmost"
    ...

def test_focus_state_activated_but_not_frontmost(...):
    # ensure_focus=True, fake probe still not frontmost after activate → "activated_but_not_frontmost"
    ...
```

Write the three assertions concretely against the real `_handle_focus` return per the implementation below.

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Users/Ben/.hfenv/bin/pytest -q -k focus`
Expected: FAIL — no `focus` key with the three states.

- [ ] **Step 3: Implement**

```python
# src/daimon/motor/organ.py — _handle_focus: add the "focus" state to each return path
        if self._focus is None or action.name not in _FOCUS_SENSITIVE:
            return {}
        window = action.params.get("window")
        if not window:
            return {}
        if window_is_frontmost(self._focus.frontmost(), window):
            return {}
        if not action.params.get("ensure_focus"):
            return {"focus": "not_attempted", "focus_warning": True,
                    "focus_detail": "target window is not frontmost; the gesture may have no effect"}
        self._activate_window(window)
        if window_is_frontmost(self._focus.frontmost(), window):
            return {"focus": "activated_and_frontmost", "focused": True}
        return {"focus": "activated_but_not_frontmost", "focused": True, "focus_warning": True,
                "focus_detail": "activated the target window but it is still not frontmost"}
```

- [ ] **Step 4: Run tests + full suite**

Run: `/Users/Ben/.hfenv/bin/pytest -q -k focus && /Users/Ben/.hfenv/bin/pytest -q`
Expected: PASS (existing focus tests still green — the new key is additive).

- [ ] **Step 5: Commit**

```bash
git add src/daimon/motor/organ.py tests/  # the focus test file you edited
git commit -m "feat(motor): three-state focus result (not_attempted / activated_and_frontmost / activated_but_not_frontmost)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Delegation imperative (a capable model MUST delegate)

**Files:**
- Modify: `src/daimon/senses/delegation.py` (`delegation_protocol_text`)
- Test: `tests/test_delegation.py`

**Interfaces:**
- `delegation_protocol_text()` makes delegation a requirement for multi-step driving while exempting one-shot perception. Still agnostic (no brand). Other functions unchanged.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_delegation.py — add (reuses the file's _BRANDS regex)
def test_protocol_makes_multistep_delegation_imperative():
    txt = delegation_protocol_text()
    low = txt.lower()
    assert "must delegate" in low                    # imperative for driving
    assert "one-shot" in low or "single vue_snapshot" in low   # perception exemption
    assert _BRANDS.search(txt) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_delegation.py::test_protocol_makes_multistep_delegation_imperative -q`
Expected: FAIL — current text says "If you can ... delegate" (not "MUST").

- [ ] **Step 3: Implement**

In `delegation_protocol_text()`, change the "If you can spawn sub-agents" bullet so the capability becomes an obligation for multi-step driving, with the one-shot exemption. Replace that bullet's lead with, e.g.:

```python
        "- If you can spawn sub-agents, you MUST delegate any multi-step UI-driving (a sequence of "
        "main_* actions / perceive→act→extract) to a sub-agent — do not drive inline; keep its "
        "screenshots out of your context and bubble up only the extracted text. Run it on a model "
        "capable of reliable multi-step tool-calling (not necessarily your smallest — a model that "
        "cannot reliably chain tool calls will stall or hallucinate a CLI; step up a tier). A "
        "one-shot perception (a single vue_snapshot to describe the screen) MAY stay inline.\n"
```

(Keep the existing "If you cannot spawn sub-agents: run inline" bullet.)

- [ ] **Step 4: Run test + full suite**

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_delegation.py -q && /Users/Ben/.hfenv/bin/pytest -q`
Expected: PASS, full suite green (the stream-B agnostic + capability tests still pass).

- [ ] **Step 5: Commit**

```bash
git add src/daimon/senses/delegation.py tests/test_delegation.py
git commit -m "feat(delegation): a capable model MUST delegate multi-step driving (one-shot exempt)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Final verification

- [ ] Full suite green: `/Users/Ben/.hfenv/bin/pytest -q` (> 393).
- [ ] No `actuator_win.py` was created on main: `test ! -f src/daimon/motor/actuator_win.py && echo OK`.
- [ ] No startup print added: `grep -rn "print(" src/daimon/server.py src/daimon/motor/actuator.py`.
- [ ] Delegation agnostic: `grep -riE "haiku|claude|gpt|gemini|opus|sonnet|llama|mistral" src/daimon/senses/delegation.py` → empty.
- [ ] `git status` clean; 6 commits on main.

## Field validation (post-merge, for Ben — not blocking)

- Lower VS Code with `main_window_hide`/`main_window_minimize` (no osascript, no Cmd+H/M), `vue_snapshot` the desktop, restore with `main_window_show`.
- `main_click` on a background window auto-focuses before clicking (no silent no-op).
- A capable orchestrator delegates a multi-step drive to a sub-agent.

## Out of scope (YAGNI)

- `main_window_close`/`quit` (destructive — separate).
- Real Windows actuator window ops (added to the existing `WindowsActuator` on `feat/windows-port` at merge).
- L4-from-tray / ceiling work (Design A, done) and stream-B prompt hardening (done).
