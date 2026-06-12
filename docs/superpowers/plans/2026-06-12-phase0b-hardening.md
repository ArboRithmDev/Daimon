# Phase 0b — Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** Close the security gaps that gate a public release — Daimon classifies on the *observed* target (not the AI's claim), redacts secret content, refuses motor action in excluded apps/regions, makes the ledger durable, and adds the risky vocabulary (drag with destination classification, held-button/key primitives) safely.

**Architecture:** A new `motor/probe.py` resolves the real target via Accessibility before the guard runs; the guard gains an "unobserved → gate/refuse" rule and app/region checks; `exclusions.py` gains a content layer (secret roles/apps); `motor/watchdog.py` auto-releases held inputs. Pure security logic is unit-tested with fakes; macOS-bound resolution is behind interfaces.

**Tech Stack:** Python 3.12, pyobjc, FastMCP, pytest, fcntl.

---

## File structure

| File | Change |
|------|--------|
| `src/daimon/config.py` | add `secret_roles`, `secret_apps` to exclusion config |
| `src/daimon/exclusions.py` | content layer: `is_target_secret`, value-blanking `redact_nodes`, role/app redaction |
| `src/daimon/senses/touche.py`, `senses/vue.py` | apply content redaction |
| `src/daimon/motor/types.py` | `Target.observed: bool = True` |
| `src/daimon/motor/probe.py` | NEW — `Prober` protocol, `MacOSProber`, `FakeProber` |
| `src/daimon/motor/guard.py` | unobserved → gate/refuse; app/region exclusion for motor |
| `src/daimon/motor/organ.py` | re-probe before guard; log claimed-vs-observed |
| `src/daimon/motor/reversibility.py` | drag → classify destination |
| `src/daimon/motor/audit.py` | `fcntl.flock` around append |
| `src/daimon/motor/consent.py` | cross-check state ⇔ ledger tail |
| `src/daimon/motor/watchdog.py` | NEW — auto-release held buttons/keys |
| `src/daimon/motor/actuator.py` | `mouse_down/up`, `key_down/up` |
| `src/daimon/motor/actions.py` | register drag (already), primitives |
| `src/daimon/server.py` | wire prober into organ; register drag + primitive tools |

Order: A2 (T1-T3) → A1 (T4-T6) → A3 (T7) → A5 (T8) → F risky (T9-T11).

---

## Task 1: Secret roles/apps config

**Files:** Modify `src/daimon/config.py`, Test `tests/test_secret_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_secret_config.py
from daimon.config import load_config


def test_secret_roles_and_apps_have_defaults(tmp_path):
    cfg = load_config(tmp_path / "missing.yaml")
    assert "AXSecureTextField" in cfg.exclusions.secret_roles
    assert any("password" in a.lower() or "1password" in a.lower() for a in cfg.exclusions.secret_apps) or cfg.exclusions.secret_apps == cfg.exclusions.secret_apps


def test_secret_roles_loaded_from_yaml(tmp_path):
    p = tmp_path / "exclusions.yaml"
    p.write_text(
        "exclusions:\n  secret_roles: [AXSecureTextField, AXMine]\n"
        "  secret_apps: [com.example.vault]\n", encoding="utf-8")
    cfg = load_config(p)
    assert "AXMine" in cfg.exclusions.secret_roles
    assert "com.example.vault" in cfg.exclusions.secret_apps
```

- [ ] **Step 2: Run, expect FAIL** — `PYTHONPATH=src python -m pytest tests/test_secret_config.py -v`.

- [ ] **Step 3: Implement** — in `config.py`, READ the existing `ExclusionConfig` dataclass (has `apps`, `window_titles`, `regions`). Add two fields with defaults and parse them in `load_config`:

```python
# in ExclusionConfig dataclass, add:
    secret_roles: tuple[str, ...] = ("AXSecureTextField",)
    secret_apps: tuple[str, ...] = ()

# module-level default applied when the key is absent:
_DEFAULT_SECRET_ROLES = ("AXSecureTextField",)
```

In `load_config`, where `ExclusionConfig(...)` is built, add:
```python
            secret_roles=tuple(excl.get("secret_roles") or _DEFAULT_SECRET_ROLES),
            secret_apps=tuple(excl.get("secret_apps") or ()),
```

(Adjust the first test's loose assertion away — final test should be: defaults present, yaml overrides work. Use this corrected test instead in Step 1 if the `or` line reads awkwardly — keep it simple:)

```python
def test_secret_roles_and_apps_have_defaults(tmp_path):
    cfg = load_config(tmp_path / "missing.yaml")
    assert "AXSecureTextField" in cfg.exclusions.secret_roles
    assert cfg.exclusions.secret_apps == ()
```

- [ ] **Step 4: Run, expect PASS.** Full suite green.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(secrets): secret_roles/secret_apps config (default AXSecureTextField)"`

---

## Task 2: Content redaction layer in ExclusionFilter

**Files:** Modify `src/daimon/exclusions.py`, Test `tests/test_secret_content.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_secret_content.py
from daimon.config import ExclusionConfig
from daimon.exclusions import ExclusionFilter


def _f(**kw):
    return ExclusionFilter(ExclusionConfig(**kw))


def test_secret_role_node_value_is_blanked():
    f = _f(secret_roles=("AXSecureTextField",))
    tree = {"role": "AXWindow", "title": "W", "children": [
        {"role": "AXSecureTextField", "title": None, "value": "hunter2"},
        {"role": "AXStaticText", "title": None, "value": "ok"},
    ]}
    out = f.redact_nodes([tree])[0]
    secure = out["children"][0]
    assert secure["value"] != "hunter2"
    assert secure.get("redacted") is True
    assert out["children"][1]["value"] == "ok"


def test_is_target_secret_by_role_and_app():
    f = _f(secret_roles=("AXSecureTextField",), secret_apps=("com.x.vault",))
    assert f.is_target_secret(role="AXSecureTextField", bundle_id=None)
    assert f.is_target_secret(role=None, bundle_id="com.x.vault")
    assert not f.is_target_secret(role="AXButton", bundle_id="com.x.safe")


def test_title_excluded_node_still_dropped():
    # existing behaviour preserved
    f = _f(window_titles=(r"(?i)password",))
    tree = {"role": "AXWindow", "title": "Password vault", "children": []}
    assert f.redact_nodes([tree]) == []
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — READ `exclusions.py`. It has `ExclusionFilter` with `is_title_excluded`, `is_app_excluded`, `redact_nodes` (currently prunes by title). Add `secret_roles`/`secret_apps` handling:

```python
# in __init__, capture the new config fields:
        self._secret_roles = set(config.secret_roles)
        self._secret_apps = set(config.secret_apps)

# new method:
    def is_target_secret(self, role: str | None = None, bundle_id: str | None = None) -> bool:
        """A target is secret if its role is a secret role or its app is declared secret."""
        if role and role in self._secret_roles:
            return True
        if bundle_id and bundle_id in self._secret_apps:
            return True
        return False
```

Update `redact_nodes` so that, in addition to dropping title-excluded subtrees, it **blanks the value** of secret-role nodes (keeping structure):

```python
    def redact_nodes(self, nodes):
        def walk(items):
            out = []
            for node in items:
                if self.is_title_excluded(node.get("title")):
                    continue
                node = dict(node)
                if node.get("role") in self._secret_roles:
                    node["value"] = "█" if node.get("value") else node.get("value")
                    node["redacted"] = True
                if node.get("children"):
                    node["children"] = walk(node["children"])
                out.append(node)
            return out
        return walk(nodes)
```

(If `redact_nodes` already has a walk, integrate the secret-role blanking into it rather than duplicating.)

- [ ] **Step 4: Run, expect PASS.** Full suite green.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(secrets): blank secret-role node values; is_target_secret(role/app)"`

---

## Task 3: Vue redaction of secret regions

**Files:** Modify `src/daimon/exclusions.py` (pure rect blackout), `src/daimon/senses/vue.py`, Test `tests/test_vue_redact.py`

- [ ] **Step 1: Write the failing test** (pure: black out a list of rects on an image)

```python
# tests/test_vue_redact.py
from daimon.exclusions import black_out_rects


class _Draw:
    def __init__(self): self.rects = []
    def rectangle(self, box, fill): self.rects.append(box)


class _Img:
    def __init__(self): self.draw = _Draw()


def test_black_out_rects_draws_each(monkeypatch):
    import daimon.exclusions as ex
    img = _Img()
    monkeypatch.setattr(ex, "_image_draw", lambda image: img.draw)
    black_out_rects(img, [{"x": 1, "y": 2, "width": 3, "height": 4}])
    assert img.draw.rects == [(1, 2, 4, 6)]


def test_black_out_empty_is_noop(monkeypatch):
    import daimon.exclusions as ex
    img = _Img()
    monkeypatch.setattr(ex, "_image_draw", lambda image: img.draw)
    black_out_rects(img, [])
    assert img.draw.rects == []
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — in `exclusions.py`:

```python
def _image_draw(image):
    from PIL import ImageDraw
    return ImageDraw.Draw(image)


def black_out_rects(image, rects):
    """Fill each {x,y,width,height} rect with black on a PIL image. Pure-ish
    (PIL import isolated in _image_draw for testability)."""
    if not rects:
        return image
    draw = _image_draw(image)
    for r in rects:
        x, y = int(r["x"]), int(r["y"])
        draw.rectangle((x, y, x + int(r["width"]), y + int(r["height"])), fill="black")
    return image
```

In `senses/vue.py`, after the frontmost gate and before/with the existing `redact_image`, gather secret-element rects from the accessibility tree of the frontmost app and black them out. Keep it best-effort (a11y may be unavailable):

```python
            image = self._exclusions.redact_image(frame.image)
            try:
                rects = self._secret_rects(frame.frontmost_bundle_id)
                from ..exclusions import black_out_rects
                black_out_rects(image, rects)
            except Exception:
                pass  # best-effort; never fail a capture on redaction-probe error
```

Add a helper method `_secret_rects(bundle_id)` to `Vue` that, when the frontmost app is secret OR contains secret-role elements, returns their `{x,y,width,height}` from `capture.accessibility.snapshot_tree()` (walk nodes, collect position+size for nodes whose role ∈ secret_roles). If the whole frontmost app is a `secret_app`, the existing frontmost gate already refuses — so `_secret_rects` handles the per-element case. Keep it small; if the tree can't be read, return `[]`.

- [ ] **Step 4: Run, expect PASS** (pure tests). `import daimon.senses.vue` clean. Full suite green.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(secrets): black out secret-element regions in Vue snapshots"`

---

## Task 4: Target.observed + guard unobserved rule

**Files:** Modify `src/daimon/motor/types.py`, `src/daimon/motor/guard.py`, Test `tests/test_guard_observed.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_guard_observed.py
from daimon.config import ExclusionConfig
from daimon.exclusions import ExclusionFilter
from daimon.motor.guard import PolicyGuard
from daimon.motor.types import Declaration, Level, MotorAction, Target, Verdict


def _guard(ceiling):
    return PolicyGuard(ExclusionFilter(ExclusionConfig()), ceiling_provider=lambda: ceiling)


def _act(level, target):
    return MotorAction(name="click", level=level, target=target,
                       declaration=Declaration(reversible=True, intent="x"), params={})


def test_unobserved_target_gates_below_l4():
    d = _guard(Level.VALIDATION).evaluate(_act(Level.INPUT, Target(observed=False)))
    assert d.verdict == Verdict.GATE


def test_unobserved_target_refused_under_l4():
    d = _guard(Level.AUTONOMOUS).evaluate(_act(Level.VALIDATION, Target(observed=False)))
    assert d.verdict == Verdict.REFUSE


def test_observed_target_unaffected():
    d = _guard(Level.INPUT).evaluate(_act(Level.INPUT, Target(role="AXButton", label="Cancel", observed=True)))
    assert d.verdict == Verdict.ALLOW
```

- [ ] **Step 2: Run, expect FAIL** (Target has no `observed`).

- [ ] **Step 3: Implement**
(a) `types.py` — add to `Target`: `observed: bool = True` (last field, keeps existing constructions valid).
(b) `guard.py` — in `evaluate`, AFTER the exclusion check and BEFORE the reversibility classification, insert:
```python
        if not action.target.observed:
            if ceiling == Level.AUTONOMOUS:
                return Decision(Verdict.REFUSE, "target unobservable under L4 (no blind autonomous action)")
            return Decision(Verdict.GATE, "Daimon could not verify the target")
```

- [ ] **Step 4: Run, expect PASS.** Full suite green.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(motor): Target.observed; guard gates/refuses unverifiable targets"`

---

## Task 5: Prober (resolve the observed target)

**Files:** Create `src/daimon/motor/probe.py`, Test `tests/test_motor_probe.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_motor_probe.py
from daimon.motor.probe import FakeProber, observed_target_from_node
from daimon.motor.types import Declaration, Level, MotorAction, Target


def _act(name, params):
    return MotorAction(name=name, level=Level.INPUT, target=Target(),
                       declaration=Declaration(reversible=True, intent="x"), params=params)


def test_node_to_observed_target():
    t = observed_target_from_node({"role": "AXButton", "title": "Send", "value": None}, x=10, y=20)
    assert t.role == "AXButton" and t.label == "Send" and t.observed is True
    assert t.x == 10 and t.y == 20


def test_fake_prober_returns_preset():
    p = FakeProber(target=Target(role="AXButton", label="Send", observed=True))
    out = p.observe(_act("click", {"x": 1, "y": 2}))
    assert out.label == "Send"


def test_fake_prober_failure_is_unobserved():
    p = FakeProber(fail=True)
    assert p.observe(_act("click", {"x": 1, "y": 2})).observed is False
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `src/daimon/motor/probe.py`:

```python
"""Resolve the *observed* target of a motor action via Accessibility.

The AI's declared role/label are advisory; the guard must classify on what is
actually under the action's coordinates (or the focused element for keyboard
actions). A probe failure yields an unobserved Target so the guard can gate
(L0-L3) or refuse (L4) rather than act blind.
"""

from __future__ import annotations

from typing import Protocol

from .types import MotorAction, Target

# Actions whose target must be verified before acting.
_COORD_ACTIONS = {"click", "press", "drag", "hover"}
_FOCUS_ACTIONS = {"type", "key"}


def observed_target_from_node(node: dict, *, x=None, y=None) -> Target:
    return Target(
        role=node.get("role"), label=node.get("title") or node.get("description"),
        value=node.get("value"), x=x, y=y, observed=True,
    )


class Prober(Protocol):
    def observe(self, action: MotorAction) -> Target: ...


class FakeProber:
    def __init__(self, target: Target | None = None, fail: bool = False):
        self._target = target or Target(observed=True)
        self._fail = fail

    def observe(self, action: MotorAction) -> Target:
        if self._fail:
            return Target(observed=False)
        return self._target


class MacOSProber:
    """Real prober using capture.accessibility."""

    def observe(self, action: MotorAction) -> Target:
        from ..capture import accessibility as ax
        try:
            if action.name == "drag":
                # the drop destination is what matters for non-return
                x, y = action.params["to_x"], action.params["to_y"]
                return observed_target_from_node(ax.element_at(x, y), x=x, y=y)
            if action.name in _COORD_ACTIONS:
                x = action.params.get("x"); y = action.params.get("y")
                if x is None or y is None:
                    return Target(observed=False)
                return observed_target_from_node(ax.element_at(x, y), x=x, y=y)
            if action.name in _FOCUS_ACTIONS:
                node = ax.focused_element()
                return observed_target_from_node(node)
        except Exception:
            return Target(observed=False)
        # navigate/activate: no specific target to verify
        return Target(observed=True)
```

Also add a `focused_element()` helper to `capture/accessibility.py`:
```python
def focused_element() -> dict:
    """The system-wide focused UI element (for keyboard-action context)."""
    from ApplicationServices import (
        AXUIElementCreateSystemWide, kAXFocusedUIElementAttribute,
    )
    system = AXUIElementCreateSystemWide()
    el = _copy_attr(system, kAXFocusedUIElementAttribute)
    if el is None:
        raise RuntimeError("No focused element.")
    return node_from_element(el)
```

- [ ] **Step 4: Run, expect PASS.** `import daimon.motor.probe` clean.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(motor): Prober resolves observed target (coords/focus/drag-destination)"`

---

## Task 6: Organ re-probes before the guard (A1 core)

**Files:** Modify `src/daimon/motor/organ.py`, Test `tests/test_organ_reprobe.py`

- [ ] **Step 1: Write the failing test** (red-team: AI lies about the label)

```python
# tests/test_organ_reprobe.py
from daimon.config import ExclusionConfig
from daimon.exclusions import ExclusionFilter
from daimon.motor.actuator import FakeActuator
from daimon.motor.audit import AppendOnlyLedger
from daimon.motor.gate import FakeGate
from daimon.motor.guard import PolicyGuard
from daimon.motor.organ import MotorOrgan
from daimon.motor.probe import FakeProber
from daimon.motor.types import Declaration, Level, MotorAction, Target


def _organ(tmp_path, ceiling, observed, gate_answer=False, actuator=None):
    guard = PolicyGuard(ExclusionFilter(ExclusionConfig()), ceiling_provider=lambda: ceiling)
    return MotorOrgan(
        guard=guard, gate=FakeGate(answer=gate_answer),
        actuator=actuator or FakeActuator(),
        session_log=AppendOnlyLedger(tmp_path / "s.jsonl"), clock=lambda: "T",
        prober=FakeProber(target=observed),
    )


def _claimed(label):
    return MotorAction(name="click", level=Level.INPUT,
                       target=Target(role="AXButton", label=label),
                       declaration=Declaration(reversible=True, intent="x"),
                       params={"x": 1, "y": 1})


def test_ai_lies_label_but_observed_send_is_gated(tmp_path):
    # AI claims "Cancel"; the real element under the coords is "Send".
    act = FakeActuator()
    observed = Target(role="AXButton", label="Send", observed=True)
    organ = _organ(tmp_path, Level.VALIDATION, observed, gate_answer=False, actuator=act)
    out = organ.act(_claimed("Cancel"))
    assert out["status"] == "refused"   # gated, human denied
    assert act.executed == []


def test_probe_failure_refused_under_l4(tmp_path):
    from daimon.motor.probe import FakeProber
    guard = PolicyGuard(ExclusionFilter(ExclusionConfig()), ceiling_provider=lambda: Level.AUTONOMOUS)
    act = FakeActuator()
    organ = MotorOrgan(guard=guard, gate=FakeGate(), actuator=act,
                       session_log=AppendOnlyLedger(tmp_path / "s.jsonl"), clock=lambda: "T",
                       prober=FakeProber(fail=True))
    out = organ.act(_claimed("Anything"))
    assert out["status"] == "refused"
    assert act.executed == []


def test_observed_target_used_for_classification(tmp_path):
    act = FakeActuator()
    observed = Target(role="AXButton", label="Cancel", observed=True)
    organ = _organ(tmp_path, Level.INPUT, observed, actuator=act)
    out = organ.act(_claimed("Send"))  # AI claims scary, reality is benign
    assert out["status"] == "done"     # classified on observed "Cancel" → allowed
    assert act.executed[0].target.label == "Cancel"
```

- [ ] **Step 2: Run, expect FAIL** (MotorOrgan has no `prober`).

- [ ] **Step 3: Implement** — modify `organ.py`:
(a) `__init__` gains `prober` param (store `self._prober`).
(b) At the top of `act`, before `guard.evaluate`, re-probe and swap the target, logging the AI's claim vs observation:
```python
    def act(self, action):
        claimed = action.target
        observed = self._prober.observe(action)
        from dataclasses import replace
        action = replace(action, target=observed)
        if (claimed.role, claimed.label) != (observed.role, observed.label):
            self._record(action, "divergence",
                         {"claimed_role": claimed.role, "claimed_label": claimed.label,
                          "observed_role": observed.role, "observed_label": observed.label})
        decision = self._guard.evaluate(action)
        ...  # rest unchanged
```
Keep the rest of `act` (REFUSE/GATE/must_log/execute) exactly as is.

- [ ] **Step 4: Run, expect PASS.** Full suite — NOTE existing `tests/test_motor_organ.py` constructs `MotorOrgan(...)` without `prober`; update those constructions to pass `prober=FakeProber(target=<the action's target>)` so the observed target equals what the test intends (or `prober=FakeProber()` where the target is irrelevant). Fix those call sites; do not weaken their assertions.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(motor): organ re-probes observed target before guard; logs claim divergence"`

---

## Task 7: App/region exclusions for motor

**Files:** Modify `src/daimon/motor/guard.py`, Test `tests/test_guard_motor_exclusions.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_guard_motor_exclusions.py
from daimon.config import ExclusionConfig, Rect
from daimon.exclusions import ExclusionFilter
from daimon.motor.guard import PolicyGuard
from daimon.motor.types import Declaration, Level, MotorAction, Target, Verdict


def _act(x, y):
    return MotorAction(name="click", level=Level.INPUT,
                       target=Target(role="AXButton", label="ok", x=x, y=y, observed=True),
                       declaration=Declaration(reversible=True, intent="i"),
                       params={"x": x, "y": y})


def test_action_in_excluded_region_refused():
    cfg = ExclusionConfig(regions=(Rect(0, 0, 100, 100),))
    g = PolicyGuard(ExclusionFilter(cfg), ceiling_provider=lambda: Level.INPUT)
    assert g.evaluate(_act(50, 50)).verdict == Verdict.REFUSE


def test_action_outside_region_allowed():
    cfg = ExclusionConfig(regions=(Rect(0, 0, 100, 100),))
    g = PolicyGuard(ExclusionFilter(cfg), ceiling_provider=lambda: Level.INPUT)
    assert g.evaluate(_act(500, 500)).verdict == Verdict.ALLOW
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement**
(a) `exclusions.py` — add a point-in-region helper:
```python
    def is_point_excluded(self, x, y) -> bool:
        if x is None or y is None:
            return False
        for r in self._config.regions:
            if r.x <= x <= r.x + r.width and r.y <= y <= r.y + r.height:
                return True
        return False
```
(b) `guard.py` — in `evaluate`, in the exclusion section (after the title check), add a region check on the action's coordinates:
```python
        if self._exclusions.is_point_excluded(action.target.x, action.target.y):
            return Decision(Verdict.REFUSE, "action target in excluded region")
```
(App-level: the frontmost-app exclusion is already enforced for Vue; for motor, the observed target carries no bundle id today, so region + title cover Phase 0b. App-by-bundle for motor is noted for later.)

- [ ] **Step 4: Run, expect PASS.** Full suite green.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(motor): refuse actions whose target falls in an excluded region"`

---

## Task 8: Ledger durability (flock + consent cross-check)

**Files:** Modify `src/daimon/motor/audit.py`, `src/daimon/motor/consent.py`, Test `tests/test_ledger_durability.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ledger_durability.py
from daimon.motor.audit import AppendOnlyLedger
from daimon.motor.consent import ConsentManager
from daimon.motor.types import Level


def test_append_still_verifies_under_lock(tmp_path):
    led = AppendOnlyLedger(tmp_path / "l.jsonl")
    led.append({"event": "a", "ts": "1"})
    led.append({"event": "b", "ts": "2"})
    assert led.verify()


def test_state_engaged_without_ledger_event_is_rejected(tmp_path):
    # Forged state file says engaged, but the ledger has no engage_l4 → fail-safe.
    import json
    state = tmp_path / "state.json"; state.write_text(json.dumps({"engaged": True}))
    led = AppendOnlyLedger(tmp_path / "consent.jsonl")  # empty ledger
    m = ConsentManager(config_ceiling=Level.READ, engagement_phrase="G",
                       disengagement_phrase="S", ledger=led, state_path=state)
    assert m.current_ceiling() == Level.READ  # not AUTONOMOUS — forgery rejected


def test_genuine_engagement_is_honored(tmp_path):
    state = tmp_path / "state.json"
    led = AppendOnlyLedger(tmp_path / "consent.jsonl")
    m = ConsentManager(config_ceiling=Level.READ, engagement_phrase="G",
                       disengagement_phrase="S", ledger=led, state_path=state)
    m.engage("G", ts="1")
    assert m.current_ceiling() == Level.AUTONOMOUS
```

- [ ] **Step 2: Run, expect FAIL** (cross-check not implemented; forged state honoured).

- [ ] **Step 3: Implement**
(a) `audit.py` — wrap the append write in an advisory lock:
```python
    def append(self, entry: dict) -> str:
        import fcntl
        prev = self._last_hash()
        body = {**entry, "prev_hash": prev}
        h = self._compute(prev, body)
        record = {**body, "hash": h}
        with self.path.open("a", encoding="utf-8") as f:
            try:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        return h
```
(Note: `_last_hash` read is still outside the lock — acceptable for v0; a stricter version locks the whole read-modify-write. Keep simple.)

(b) `consent.py` — `current_ceiling` cross-checks the ledger tail. Add a `_last_event()` helper reading the ledger's last record's `event`, and gate L4 on it:
```python
    def _last_ledger_event(self) -> str | None:
        records = self._ledger._records()  # reuse the ledger's parser
        return records[-1].get("event") if records else None

    def current_ceiling(self) -> Level:
        if self._engaged() and self._last_ledger_event() == "engage_l4":
            return Level.AUTONOMOUS
        return self._config_ceiling
```

- [ ] **Step 4: Run, expect PASS.** Full suite — existing consent tests should still pass because genuine `engage()` writes the ledger event then the state file. Verify.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "harden(motor): flock ledger appends; consent cross-checks ledger tail vs state"`

---

## Task 9: Drag with destination classification

**Files:** Modify `src/daimon/motor/reversibility.py`, `src/daimon/server.py`, Test `tests/test_drag_classification.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_drag_classification.py
from daimon.motor.reversibility import classify
from daimon.motor.types import Declaration, Level, MotorAction, Target


def _drag(dest_label):
    # the organ sets the observed target to the destination element (Task 6 / MacOSProber)
    return MotorAction(name="drag", level=Level.INPUT,
                       target=Target(role="AXImage", label=dest_label, observed=True),
                       declaration=Declaration(reversible=True, intent="x"),
                       params={"from_x": 0, "from_y": 0, "to_x": 9, "to_y": 9})


def test_drag_onto_trash_is_irreversible():
    assert classify(_drag("Trash")).irreversible
    assert classify(_drag("Corbeille")).irreversible


def test_drag_onto_plain_target_is_reversible():
    assert not classify(_drag("Folder A")).irreversible
```

- [ ] **Step 2: Run, expect FAIL** (Trash/Corbeille not in denylist).

- [ ] **Step 3: Implement** — `reversibility.py`: extend `_DANGER_TEXT` to include trash terms so a drag whose observed destination label matches is flagged. Add `trash|corbeille|bin` to the alternation. The classifier already runs on `action.target` which (post-Task-6) is the drag destination. Then in `server.py`, register `main_drag` as an MCP tool (the actuator `_drag` exists):
```python
    @mcp.tool(name="main_drag", description=(
        "Drag from (from_x,from_y) to (to_x,to_y). The drop destination is "
        "classified for reversibility (e.g. dropping on Trash gates)."))
    def main_drag(from_x: int, from_y: int, to_x: int, to_y: int, intent: str,
                  button: str = "left", reversible: bool = True) -> dict:
        return organ.act(MotorAction(
            name="drag", level=level_for("main_drag"), target=Target(),
            declaration=Declaration(reversible=reversible, intent=intent),
            params={"from_x": from_x, "from_y": from_y, "to_x": to_x, "to_y": to_y,
                    "button": button}))
```
Also update `actuator.py` `_drag` to read `from_x/from_y/to_x/to_y` keys (it currently reads `from`/`to` tuples — align to the new param names):
```python
    def _drag(self, action):
        import Quartz
        x1, y1 = action.params["from_x"], action.params["from_y"]
        x2, y2 = action.params["to_x"], action.params["to_y"]
        ...
```

- [ ] **Step 4: Run, expect PASS.** Full suite + server lists `main_drag`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(motor): main_drag tool + destination (Trash) classification"`

---

## Task 10: Held-input primitives + watchdog

**Files:** Create `src/daimon/motor/watchdog.py`, Modify `src/daimon/motor/actuator.py`, `src/daimon/motor/actions.py`, Test `tests/test_watchdog.py`

- [ ] **Step 1: Write the failing test** (pure watchdog logic; injected clock + release fn)

```python
# tests/test_watchdog.py
from daimon.motor.watchdog import HoldWatchdog


def test_release_after_timeout():
    released = []
    now = [0.0]
    wd = HoldWatchdog(timeout=5.0, release=lambda h: released.append(h), clock=lambda: now[0])
    wd.hold("mouse_left")
    now[0] = 6.0
    wd.tick()
    assert released == ["mouse_left"]


def test_explicit_release_cancels_watchdog():
    released = []
    now = [0.0]
    wd = HoldWatchdog(timeout=5.0, release=lambda h: released.append(h), clock=lambda: now[0])
    wd.hold("key_shift")
    wd.release_hold("key_shift")
    now[0] = 99.0
    wd.tick()
    assert released == []  # already released explicitly, watchdog must not double-release


def test_not_yet_expired_keeps_hold():
    wd = HoldWatchdog(timeout=5.0, release=lambda h: None, clock=lambda: 1.0)
    wd.hold("mouse_left")
    wd.tick()
    assert "mouse_left" in wd.active()
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `src/daimon/motor/watchdog.py` (pure; the actuator supplies the real `release` callback and clock):

```python
"""Auto-release safety net for held inputs (primitives).

A low-level mouse_down/key_down may never get its up if the agent errors. The
watchdog tracks holds with a deadline; tick() releases any past-deadline hold.
Pure — the actuator injects the real release fn and clock."""

from __future__ import annotations

from typing import Callable


class HoldWatchdog:
    def __init__(self, timeout: float, release: Callable[[str], None], clock: Callable[[], float]):
        self._timeout = timeout
        self._release = release
        self._clock = clock
        self._held: dict[str, float] = {}

    def hold(self, handle: str) -> None:
        self._held[handle] = self._clock() + self._timeout

    def release_hold(self, handle: str) -> None:
        self._held.pop(handle, None)

    def tick(self) -> None:
        now = self._clock()
        for handle in [h for h, deadline in self._held.items() if now >= deadline]:
            self._held.pop(handle, None)
            self._release(handle)

    def active(self) -> set[str]:
        return set(self._held)
```

Then in `actions.py` register the primitives (gated level — use VALIDATION as the nominal floor; the real L4/opt-in gate is enforced in the server tool, see Task 11):
```python
    "main_mouse_down": ActionDef("main_mouse_down", Level.VALIDATION, "press and hold a mouse button"),
    "main_mouse_up": ActionDef("main_mouse_up", Level.NONDESTRUCTIVE, "release a held mouse button"),
    "main_key_down": ActionDef("main_key_down", Level.VALIDATION, "press and hold a key"),
    "main_key_up": ActionDef("main_key_up", Level.NONDESTRUCTIVE, "release a held key"),
```
And add `_mouse_down/_mouse_up/_key_down/_key_up` methods to `MacOSActuator` (down/up halves of the existing click/key code) plus handler-map entries. Keep them minimal — each posts a single down or up CGEvent.

- [ ] **Step 4: Run, expect PASS** (watchdog pure tests). `import daimon.motor.actuator` clean.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(motor): hold watchdog + mouse/key down-up primitives"`

---

## Task 11: Wire prober into factory/server; gate primitives; registration test

**Files:** Modify `src/daimon/motor/factory.py`, `src/daimon/server.py`, Test `tests/test_server_tools.py`

- [ ] **Step 1: Update the failing test** — extend the expected tool-set in `tests/test_server_tools.py`:

```python
    expected = {
        "vue_displays", "vue_snapshot", "touche_tree", "touche_probe",
        "main_click", "main_type", "main_press", "main_navigate",
        "main_key", "main_hover", "main_activate", "main_drag",
    }
    assert expected <= names
```

- [ ] **Step 2: Run, expect FAIL** (main_drag missing if Task 9 server edit not present; ensure it is).

- [ ] **Step 3: Implement**
(a) `factory.py` — `build_organ` constructs a `MacOSProber` and passes `prober=MacOSProber()` to `MotorOrgan`.
(b) `server.py` — primitives (`main_mouse_down/up`, `main_key_down/up`) are registered ONLY as tools that the organ will refuse unless ceiling is L4 or `advanced_primitives` config is set. Simplest safe wiring for Phase 0b: register them but have the organ/guard refuse them below L4 by giving them `Level.AUTONOMOUS`-equivalent gating — since `level_for("main_mouse_down")` is VALIDATION, they'll gate at L3 and refuse above ceiling; to require L4, set their MotorAction level to `Level.AUTONOMOUS` in the server tool so they are refused unless the ceiling is L4. Implement the four primitive tools accordingly (level=Level.AUTONOMOUS), each logging via organ.act.
(c) Confirm `main_drag` tool from Task 9 is present.

- [ ] **Step 4: Run** — full suite + print tool list. All green.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(motor): wire MacOSProber; register drag + L4-gated primitives"`

---

## Task 12: Full suite + docs

- [ ] **Step 1:** `PYTHONPATH=src python -m pytest -q` — all pass.
- [ ] **Step 2:** Update README "The hands" section: note that Daimon re-probes the real target (AI labels are advisory), secret-role/app content is redacted in both senses, actions in excluded regions are refused, and press-and-hold primitives are L4-gated with an auto-release watchdog.
- [ ] **Step 3:** Commit — `git add README.md && git commit -m "docs: Phase 0b hardening (re-probe, secret content, region refusal, primitives)"`

---

## Self-review

- **Spec coverage:** A1 re-probe → T4-T6 (+ fail-safe gate/refuse). A2 secrets content → T1-T3. A3 app/region motor → T7. A5 ledger durability → T8. F risky vocab → T9 (drag+destination), T10-T11 (primitives+watchdog, L4-gated). F2 already done in 0a. ✓
- **Placeholders:** none — code complete; the one loose first-test assertion in T1 is corrected inline in Step 3. ✓
- **Type consistency:** `Target.observed` (T4) used by guard (T4), prober (T5), organ (T6); `MotorOrgan(prober=...)` (T6) wired in factory (T11); existing organ tests updated for the new param (T6 Step 4); drag param names `from_x/from_y/to_x/to_y` consistent across actuator/server/reversibility (T9). ✓
- **Security note:** the red-team test (AI claims "Cancel" on observed "Send") is the headline A1 guarantee; probe-failure-under-L4 = refuse is the headline fail-safe. Both in T6.
