# Tray — Resident menu-bar control surface — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`).

**Goal:** A persistent native menu-bar app (NSStatusItem) to see Daimon's status and change settings (motor ceiling, overlay) day to day, re-run onboarding, and quit — without a Dock icon.

**Architecture:** Pure core (state dataclasses, declarative menu model, settings writers) under a thin AppKit `NSStatusItem` layer. The tray and the MCP servers are separate processes communicating via config files (as `motor.state.json` already does). All pure logic is unit-tested; the AppKit layer is smoke-only.

**Tech Stack:** Python 3.12, pyobjc (AppKit, deferred), PyYAML, pytest.

---

## File structure

| File | Responsibility |
|------|----------------|
| `src/daimon/tray/__init__.py` | package doc |
| `src/daimon/tray/state.py` | `ClientStatus`, `TrayState` dataclasses + thin `gather()` reader |
| `src/daimon/tray/menu_model.py` | PURE `MenuItem` + `build_menu(state)` |
| `src/daimon/tray/settings.py` | `set_ceiling`/`set_overlay` — yaml writers (clamp L4, preserve keys, atomic, backup) |
| `src/daimon/tray/app/__main__.py`, `app/statusitem.py` | AppKit NSStatusItem (smoke) |
| `src/daimon/__main__.py` | frozen no-arg → tray app |
| `tests/test_tray_*` | per task |

Order: state → menu_model → settings → dispatch → GUI → docs.

---

## Task 1: State dataclasses

**Files:** Create `src/daimon/tray/__init__.py`, `src/daimon/tray/state.py`, `tests/test_tray_state.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tray_state.py
from daimon.tray.state import ClientStatus, TrayState
from daimon.motor.types import Level


def test_tray_state_holds_fields():
    s = TrayState(
        version="1.2.3", screen_ok=True, accessibility_ok=False,
        clients=(ClientStatus("Claude Code", True), ClientStatus("Cursor", False)),
        ceiling=Level.INPUT, l4_active=False, overlay_on=True,
    )
    assert s.version == "1.2.3"
    assert s.screen_ok and not s.accessibility_ok
    assert s.clients[0].registered and not s.clients[1].registered
    assert s.ceiling == Level.INPUT and s.overlay_on and not s.l4_active
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement**

`src/daimon/tray/__init__.py`:
```python
"""Tray — Daimon's resident menu-bar control surface.

A native NSStatusItem app for day-to-day status + settings. Pure core (state /
menu model / settings writers) under a thin AppKit layer; the tray and the MCP
servers are separate processes that share state through config files.
"""
```

`src/daimon/tray/state.py`:
```python
"""Aggregated tray state + a thin reader that gathers it from the real sources."""

from __future__ import annotations

from dataclasses import dataclass

from ..motor.types import Level


@dataclass(frozen=True)
class ClientStatus:
    name: str
    registered: bool


@dataclass(frozen=True)
class TrayState:
    version: str
    screen_ok: bool
    accessibility_ok: bool
    clients: tuple[ClientStatus, ...]
    ceiling: Level
    l4_active: bool
    overlay_on: bool


def gather() -> TrayState:
    """Read the real sources (config + permission marker + client registry).

    Thin and side-effecting (filesystem reads) — exercised by the live app, not
    unit tests, which construct TrayState directly.
    """
    from .. import __version__
    from ..config import load_motor_config, load_overlay_config
    from ..setup.clients.base import status as client_status
    from ..setup.clients.registry import default_adapters, detected
    from ..setup.permissions import read_status

    perms = read_status()
    motor = load_motor_config()
    overlay = load_overlay_config()
    clients = tuple(
        ClientStatus(a.name, client_status(a, "daimon").action == "present")
        for a in detected(default_adapters())
    )
    return TrayState(
        version=__version__,
        screen_ok=bool(perms.get("screen_recording")),
        accessibility_ok=bool(perms.get("accessibility")),
        clients=clients,
        ceiling=motor.ceiling,
        l4_active=False,  # L4 is runtime/consent-gated; shown read-only if engaged
        overlay_on=overlay.enabled,
    )
```

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(tray): TrayState/ClientStatus + thin gather() reader"`

---

## Task 2: Declarative menu model (pure)

**Files:** Create `src/daimon/tray/menu_model.py`, `tests/test_tray_menu.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tray_menu.py
from daimon.tray.menu_model import MenuItem, build_menu
from daimon.tray.state import ClientStatus, TrayState
from daimon.motor.types import Level


def _state(**kw):
    base = dict(version="1.0.0", screen_ok=True, accessibility_ok=True,
                clients=(ClientStatus("Claude Code", True),),
                ceiling=Level.INPUT, l4_active=False, overlay_on=False)
    base.update(kw)
    return TrayState(**base)


def _ids(items):
    out = []
    for it in items:
        out.append(it.action_id or it.kind)
        out.extend(_ids(it.children))
    return out


def test_menu_has_status_settings_and_actions():
    items = build_menu(_state())
    ids = _ids(items)
    assert "run_setup" in ids and "quit" in ids and "toggle_overlay" in ids
    assert "set_ceiling:READ" in ids and "set_ceiling:VALIDATION" in ids


def test_ceiling_submenu_marks_current_and_excludes_l4():
    items = build_menu(_state(ceiling=Level.INPUT))
    ceiling = next(i for i in items if i.kind == "submenu" and "lafond" in i.label or "eiling" in i.label.lower())
    radios = {i.action_id: i for i in ceiling.children if i.kind == "radio"}
    assert "set_ceiling:AUTONOMOUS" not in radios          # L4 never settable from the menu
    assert radios["set_ceiling:INPUT"].checked is True       # current marked
    assert radios["set_ceiling:READ"].checked is False


def test_overlay_checkbox_reflects_state():
    on = next(i for i in build_menu(_state(overlay_on=True)) if i.action_id == "toggle_overlay")
    off = next(i for i in build_menu(_state(overlay_on=False)) if i.action_id == "toggle_overlay")
    assert on.checked is True and off.checked is False


def test_permission_labels_show_status():
    items = build_menu(_state(screen_ok=False, accessibility_ok=True))
    labels = [i.label for i in items if i.kind == "label"]
    assert any("Screen Recording" in l and ("⚪" in l or "missing" in l.lower() or "❌" in l) for l in labels)
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `src/daimon/tray/menu_model.py`:
```python
"""Pure declarative menu model. The AppKit layer renders these items and routes
their action_id; keeping the structure here makes the menu logic unit-testable
and Windows-portable."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..motor.types import Level
from .state import TrayState

# Ceilings the menu may set — L4 (AUTONOMOUS) is intentionally excluded: it
# requires written consent via the control CLI, never a menu click.
_SETTABLE_CEILINGS = (Level.READ, Level.NONDESTRUCTIVE, Level.INPUT, Level.VALIDATION)


@dataclass(frozen=True)
class MenuItem:
    kind: str                      # label|separator|action|radio|checkbox|submenu
    label: str = ""
    action_id: str = ""
    checked: bool = False
    enabled: bool = True
    children: tuple = field(default_factory=tuple)


def _dot(ok: bool) -> str:
    return "✅" if ok else "⚪"


def build_menu(state: TrayState) -> list[MenuItem]:
    ceiling_children = tuple(
        MenuItem(kind="radio", label=lvl.name, action_id=f"set_ceiling:{lvl.name}",
                 checked=(state.ceiling == lvl))
        for lvl in _SETTABLE_CEILINGS
    )
    clients_children = tuple(
        MenuItem(kind="label", label=f"{c.name}  {_dot(c.registered)}")
        for c in state.clients
    ) or (MenuItem(kind="label", label="No AI clients detected", enabled=False),)

    items: list[MenuItem] = [
        MenuItem(kind="label", label=f"Daimon v{state.version}", enabled=False),
        MenuItem(kind="separator"),
        MenuItem(kind="label", label=f"👁 Screen Recording  {_dot(state.screen_ok)}", enabled=False),
        MenuItem(kind="label", label=f"✋ Accessibility  {_dot(state.accessibility_ok)}", enabled=False),
        MenuItem(kind="submenu", label=f"Clients ({sum(c.registered for c in state.clients)})",
                 children=clients_children),
        MenuItem(kind="separator"),
        MenuItem(kind="submenu", label=f"Hands ceiling: {state.ceiling.name}",
                 children=ceiling_children),
        MenuItem(kind="checkbox", label="Show overlay", action_id="toggle_overlay",
                 checked=state.overlay_on),
    ]
    if state.l4_active:
        items.append(MenuItem(kind="label", label="⚠️ L4 AUTONOMY ACTIVE", enabled=False))
    items += [
        MenuItem(kind="separator"),
        MenuItem(kind="action", label="Run setup…", action_id="run_setup"),
        MenuItem(kind="action", label="Open config folder", action_id="open_config"),
        MenuItem(kind="action", label="Open logs", action_id="open_logs"),
        MenuItem(kind="separator"),
        MenuItem(kind="action", label="Quit Daimon", action_id="quit"),
    ]
    return items
```

- [ ] **Step 4: Run, expect PASS.** (Note: the test's submenu lookup is loose; ensure the ceiling submenu label contains "ceiling".)
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(tray): pure declarative menu model (status/ceiling/overlay/actions)"`

---

## Task 3: Settings writers

**Files:** Create `src/daimon/tray/settings.py`, `tests/test_tray_settings.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tray_settings.py
from daimon.config import load_motor_config, load_overlay_config
from daimon.motor.types import Level
from daimon.tray.settings import set_ceiling, set_overlay


def test_set_ceiling_writes_and_preserves_l4_phrases(tmp_path):
    p = tmp_path / "motor.yaml"
    p.write_text("motor:\n  ceiling: READ\n  l4:\n    engagement_phrase: GO\n", encoding="utf-8")
    set_ceiling("INPUT", path=p)
    cfg = load_motor_config(p)
    assert cfg.ceiling == Level.INPUT
    assert cfg.engagement_phrase == "GO"   # preserved


def test_set_ceiling_clamps_l4(tmp_path):
    p = tmp_path / "motor.yaml"
    set_ceiling("AUTONOMOUS", path=p)
    assert load_motor_config(p).ceiling == Level.VALIDATION   # clamped, never L4


def test_set_overlay_writes(tmp_path):
    p = tmp_path / "overlay.yaml"
    set_overlay(True, path=p)
    assert load_overlay_config(p).enabled is True
    set_overlay(False, path=p)
    assert load_overlay_config(p).enabled is False


def test_set_ceiling_backs_up_existing(tmp_path):
    p = tmp_path / "motor.yaml"
    p.write_text("motor:\n  ceiling: READ\n", encoding="utf-8")
    set_ceiling("INPUT", path=p)
    assert any(x.name.startswith("motor.yaml.bak") for x in tmp_path.iterdir())
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `src/daimon/tray/settings.py`:
```python
"""Write the settings the menu can change (motor ceiling, overlay on/off).

Atomic + backup + key-preserving. The ceiling is clamped to VALIDATION — L4
never comes from a menu click (it needs written consent via the control CLI)."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from ..motor.types import Level


def _read(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    data = yaml.safe_load(text)
    return data if isinstance(data, dict) else {}


def _write(path: Path, data: dict, ts: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.with_name(f"{path.name}.bak.{ts}").write_text(
            path.read_text(encoding="utf-8"), encoding="utf-8")
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    os.replace(tmp, path)


def _ts() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def set_ceiling(name: str, path: Path) -> None:
    try:
        level = Level[name.strip().upper()]
    except KeyError:
        return
    if level > Level.VALIDATION:        # never L4 from a menu
        level = Level.VALIDATION
    data = _read(path)
    motor = data.setdefault("motor", {})
    if not isinstance(motor, dict):
        motor = {}
        data["motor"] = motor
    motor["ceiling"] = level.name
    _write(path, data, _ts())


def set_overlay(enabled: bool, path: Path) -> None:
    data = _read(path)
    overlay = data.setdefault("overlay", {})
    if not isinstance(overlay, dict):
        overlay = {}
        data["overlay"] = overlay
    overlay["enabled"] = bool(enabled)
    _write(path, data, _ts())
```

- [ ] **Step 4: Run, expect PASS.**
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(tray): settings writers (ceiling clamp+preserve, overlay) atomic+backup"`

---

## Task 4: Dispatch frozen no-arg → tray

**Files:** Modify `src/daimon/__main__.py`, Test `tests/test_main_dispatch.py`

- [ ] **Step 1: Add the failing test** (append to `tests/test_main_dispatch.py`)

```python
def test_no_arg_frozen_runs_tray(monkeypatch):
    monkeypatch.setattr(m.sys, "frozen", True, raising=False)
    ran = {}
    monkeypatch.setattr("daimon.tray.app.__main__.main", lambda: ran.setdefault("tray", True) or 0)
    m.main([])
    assert ran.get("tray") is True
```

(Update/replace the existing `test_no_arg_frozen_runs_gui` — frozen no-arg now opens the resident tray, not the one-shot GUI. The tray itself opens onboarding on first run.)

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — in `__main__.py`, change `_run_gui` usage for the frozen-no-arg branch to a new `_run_tray`:
```python
def _run_tray() -> int:
    from .tray.app.__main__ import main as tray_main
    return tray_main()
```
and in `main`, the `if not argv:` frozen branch calls `_run_tray()` instead of `_run_gui()`. Keep `--gui` → `_run_gui()` (onboarding window). Update the module docstring accordingly.

- [ ] **Step 4: Run, expect PASS.** Full suite green.
- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(app): frozen no-arg launches the resident menu-bar tray"`

---

## Task 5: AppKit NSStatusItem (smoke)

**Files:** Create `src/daimon/tray/app/__init__.py`, `app/statusitem.py`, `app/__main__.py`

No unit tests. Acceptance = clean bare import (deferred AppKit) + the status item renders the menu model and routes actions.

- [ ] **Step 1:** `app/__init__.py`: docstring.

- [ ] **Step 2:** `app/statusitem.py` — `StatusItemController`: creates an `NSStatusItem`, builds an `NSMenu` from `menu_model.build_menu(state.gather())`, wires actions, polls. All AppKit/objc imports inside methods; the action target uses the same lazy-`_ButtonTarget(NSObject)` pattern as `setup/gui/window.py` (factor or duplicate the tiny `_make_target`). Action routing maps `action_id`:
  - `set_ceiling:<NAME>` → `settings.set_ceiling(NAME, motor_config_path)`
  - `toggle_overlay` → `settings.set_overlay(not current, overlay_config_path)`
  - `run_setup` → open onboarding window (`setup.gui.window.OnboardingController(MacOSBackend()).show()`)
  - `open_config` / `open_logs` → `subprocess.run(["open", <dir>])`
  - `quit` → `NSApp.terminate_(None)`
  Rebuild the menu after any setting change and on a ~2s poll. Use the config paths from `daimon.config` (`_MOTOR_DEFAULT`, `_OVERLAY_DEFAULT`) for writes.

- [ ] **Step 3:** `app/__main__.py`:
```python
"""Resident menu-bar entry: NSApplication (accessory, no Dock) + NSStatusItem."""

from __future__ import annotations


def main() -> int:
    from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
    from PyObjCTools import AppHelper
    from .statusitem import StatusItemController

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)  # menu-bar only
    StatusItemController().install()
    AppHelper.runEventLoop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4:** Verify bare imports: `PYTHONPATH=src python -c "import daimon.tray.app.statusitem, daimon.tray.app.__main__"` → clean (no AppKit at import). Full suite green.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(tray): NSStatusItem app (menu render + action routing, smoke)"`

---

## Task 6: Docs + suite

- [ ] **Step 1:** `PYTHONPATH=src python -m pytest -q` — all pass.
- [ ] **Step 2:** README — add a short "## The menu bar (resident control surface)" note: double-clicking Daimon.app puts a menu-bar icon (no Dock) showing permission/client status and letting you set the hands ceiling (L0–L3; L4 stays consent-gated), toggle the overlay, re-run setup, and quit. First run opens onboarding automatically.
- [ ] **Step 3:** Commit — `git add README.md && git commit -m "docs: resident menu-bar control surface"`

---

## Self-review

- **Spec coverage:** §3 menu → menu_model (T2); §4 state/settings → T1/T3; §5 dispatch → T4; AppKit → T5; docs → T6. ✓
- **Invariants:** L4 never settable from the menu — `_SETTABLE_CEILINGS` excludes AUTONOMOUS (T2) AND `set_ceiling` clamps (T3); never corrupt yaml — atomic+backup+preserve (T3); separate processes via config files (no new IPC). ✓
- **Type consistency:** `TrayState`/`ClientStatus` (T1) consumed by `build_menu` (T2) and `gather` (T1); `MenuItem.action_id` strings (`set_ceiling:<NAME>`, `toggle_overlay`, `run_setup`, `open_config`, `open_logs`, `quit`) are the contract the AppKit router implements (T5); `set_ceiling(name, path)` / `set_overlay(bool, path)` signatures consistent (T3/T5). ✓
