# Daimon "Face" — Webview UI Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Render the Claude Design UI in system webviews (pywebview) for three surfaces — menu-bar panel, on-screen overlay face, onboarding — bound to the organ through a typed JS↔Python bridge, with all authority kept in the organ.

**Architecture:** A new OS-agnostic `src/daimon/face/` package hosts three pywebview windows loading a locally-built web bundle. A pure `view_model` serializes the existing `TrayState` to JSON; a shared `ActionRouter` (extracted from today's AppKit `_dispatch`) routes user intent for BOTH the native `NSMenu` and the face bridge; per-OS window traits (vibrancy/anchor/capture-exclusion) live behind `face/platform/` adapters. The overlay surface wraps the existing MCP `overlay_*` engine and preserves screen-capture-exclusion.

**Tech Stack:** Python 3.12 (macOS) / 3.13 (Windows), pywebview (system WKWebView/WebView2), pyobjc (AppKit/Quartz vibrancy+anchor+exclusion), Node 26 + esbuild (web bundle, via `npx`), vendored React 18, FastMCP, pytest.

## Global Constraints

- **Suite stays green:** `/Users/Ben/.hfenv/bin/pytest -q` (currently 405). New pure-Python seams are unit-tested headless; native windowing is manual real-machine validation, guarded to skip off-platform.
- **The web layer is presentational ONLY.** It never receives secrets or perception content. Perception, secret redaction, and the **L0–L4 Hands ceiling stay enforced in the organ.** The bridge is a typed allowlist and **cannot raise the ceiling** (L4 requires the native consent dialog + ledger).
- **Webview loads only local bundled assets.** CSP `default-src 'self'`; no remote origins anywhere in `face/web/dist`; verified by a grep gate.
- **Real ceiling ladder:** `L0 READ · L1 NONDESTRUCTIVE · L2 INPUT · L3 VALIDATION` are settable; **`L4 AUTONOMOUS` is consent-gated, never a slider stop.** The CD mock's `Observe/Assist/Act/Control` names are wrong and must not appear.
- **Brand track is locked** (no production tweaks panel): Presence Purple `#B66CFF`, Companion Amber `#E8B23A`, indigo tile, `beside` organic.
- **Overlay stays screen-capture-excluded** (`NSWindowSharingNone` / `WDA_EXCLUDEFROMCAPTURE`) and **wraps** the existing `overlay_*` draw engine — that engine is untouched.
- **pywebview is a darwin/win-guarded dependency**; importing `face.host` must not hard-fail on a machine without it at unit-test time (lazy import).
- Conventional commits; end bodies with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- **Phasing of effort:** Phases 0–2 are OS-agnostic + TDD headless (agent-implementable now). Phases 3–6 need pywebview installed + a real Mac/Win (native windowing) — their pure seams are still unit-tested; window behavior is manual validation.

## File Structure

```
src/daimon/tray/actions.py        NEW  ActionRouter + ActionHandlers protocol (shared dispatch)
src/daimon/tray/app/statusitem.py MOD  _dispatch delegates to ActionRouter
src/daimon/face/__init__.py       NEW  package
src/daimon/face/view_model.py     NEW  pure TrayState -> JSON view contract + brand constants
src/daimon/face/bridge.py         NEW  FaceBridge (get_state / invoke) over ActionRouter
src/daimon/face/host.py           NEW  pywebview window lifecycle for the 3 surfaces (lazy import)
src/daimon/face/platform/__init__.py NEW  adapter selector
src/daimon/face/platform/macos.py NEW  vibrancy / anchor / capture-exclusion (pyobjc)
src/daimon/face/platform/windows.py NEW scaffold (acrylic / tray-anchor / WDA exclude)
src/daimon/face/web/src/...        NEW  de-playgrounded CD components + bridge.js
src/daimon/face/web/dist/...       BUILD esbuild output (gitignored except a marker)
build/make_face.py                 NEW  esbuild bundle builder (npx)
tests/test_tray_actions.py         NEW  ActionRouter routing
tests/test_face_view_model.py      NEW  serialize golden
tests/test_face_bridge.py          NEW  bridge get_state/invoke/allowlist
tests/test_face_bundle.py          NEW  bundle smoke (dist exists, CSP, no remote URLs)
tests/test_face_host.py            NEW  host wiring (with a fake webview)
```

---

## Phase 0 — Shared action router (refactor, enables the bridge)

### Task 1: Extract `ActionRouter` from the AppKit `_dispatch`

**Files:**
- Create: `src/daimon/tray/actions.py`
- Test: `tests/test_tray_actions.py`

**Interfaces:**
- Produces: `ActionResult(ok: bool, reason: str = "")`; `ActionHandlers` (Protocol with `set_ceiling(name: str)`, `toggle_overlay()`, `install_all()`, `toggle_client(name: str)`, `engage_l4()`, `disengage_l4()`, `run_setup()`, `open_config()`, `open_logs()`, `quit()`, each returning `None`); `ActionRouter(handlers: ActionHandlers)` with `dispatch(action_id: str) -> ActionResult`.
- Consumed by: Task 2 (statusitem), Task 5 (bridge).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tray_actions.py
from daimon.tray.actions import ActionRouter, ActionResult


class _Rec:
    def __init__(self): self.calls = []
    def set_ceiling(self, name): self.calls.append(("set_ceiling", name))
    def toggle_overlay(self): self.calls.append(("toggle_overlay",))
    def install_all(self): self.calls.append(("install_all",))
    def toggle_client(self, name): self.calls.append(("toggle_client", name))
    def engage_l4(self): self.calls.append(("engage_l4",))
    def disengage_l4(self): self.calls.append(("disengage_l4",))
    def run_setup(self): self.calls.append(("run_setup",))
    def open_config(self): self.calls.append(("open_config",))
    def open_logs(self): self.calls.append(("open_logs",))
    def quit(self): self.calls.append(("quit",))


def test_router_dispatches_parameterized_actions():
    rec = _Rec(); r = ActionRouter(rec)
    assert r.dispatch("set_ceiling:INPUT") == ActionResult(True, "")
    assert r.dispatch("toggle_client:Claude") == ActionResult(True, "")
    assert ("set_ceiling", "INPUT") in rec.calls
    assert ("toggle_client", "Claude") in rec.calls


def test_router_dispatches_simple_actions():
    rec = _Rec(); r = ActionRouter(rec)
    for aid, expect in [("toggle_overlay", "toggle_overlay"), ("install_all", "install_all"),
                        ("engage_l4", "engage_l4"), ("quit", "quit")]:
        assert r.dispatch(aid).ok
        assert (expect,) in rec.calls


def test_router_rejects_unknown_action():
    res = ActionRouter(_Rec()).dispatch("rm_-rf")
    assert res.ok is False and "unknown" in res.reason.lower()


def test_router_never_sets_ceiling_to_l4():
    # L4 is consent-gated; set_ceiling:AUTONOMOUS must be refused, not routed.
    rec = _Rec()
    res = ActionRouter(rec).dispatch("set_ceiling:AUTONOMOUS")
    assert res.ok is False and "l4" in res.reason.lower()
    assert rec.calls == []
```

- [ ] **Step 2: Run — FAIL** (`ModuleNotFoundError: daimon.tray.actions`)

Run: `/Users/Ben/.hfenv/bin/pytest tests/test_tray_actions.py -q`

- [ ] **Step 3: Implement**

```python
# src/daimon/tray/actions.py
"""Renderer-agnostic action router. The AppKit menu and the webview face both
dispatch user intent through here, so the routing is testable and shared. The
router only knows a fixed allowlist of action_ids; it carries no effects of its
own — it calls the injected handlers, which own the side effects (and their own
gating, e.g. the L4 consent dialog lives behind engage_l4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ActionResult:
    ok: bool
    reason: str = ""


class ActionHandlers(Protocol):
    def set_ceiling(self, name: str) -> None: ...
    def toggle_overlay(self) -> None: ...
    def install_all(self) -> None: ...
    def toggle_client(self, name: str) -> None: ...
    def engage_l4(self) -> None: ...
    def disengage_l4(self) -> None: ...
    def run_setup(self) -> None: ...
    def open_config(self) -> None: ...
    def open_logs(self) -> None: ...
    def quit(self) -> None: ...


# Ceilings the UI may set directly. AUTONOMOUS (L4) is intentionally absent — it
# is reached only via engage_l4 (native consent dialog + ledger).
_SETTABLE = {"READ", "NONDESTRUCTIVE", "INPUT", "VALIDATION"}
_SIMPLE = {
    "toggle_overlay", "install_all", "engage_l4", "disengage_l4",
    "run_setup", "open_config", "open_logs", "quit",
}


class ActionRouter:
    """Parse an action_id and call the matching handler. Returns an ActionResult;
    never raises for an unknown id (it refuses)."""

    def __init__(self, handlers: ActionHandlers) -> None:
        self._h = handlers

    def dispatch(self, action_id: str) -> ActionResult:
        if action_id.startswith("set_ceiling:"):
            name = action_id[len("set_ceiling:"):]
            if name == "AUTONOMOUS":
                return ActionResult(False, "L4 is consent-gated; use engage_l4")
            if name not in _SETTABLE:
                return ActionResult(False, f"unknown ceiling: {name}")
            self._h.set_ceiling(name)
            return ActionResult(True)
        if action_id.startswith("toggle_client:"):
            self._h.toggle_client(action_id[len("toggle_client:"):])
            return ActionResult(True)
        if action_id in _SIMPLE:
            getattr(self._h, action_id)()
            return ActionResult(True)
        return ActionResult(False, f"unknown action: {action_id}")
```

- [ ] **Step 4: Run — PASS.** Then full suite: `/Users/Ben/.hfenv/bin/pytest -q`.

- [ ] **Step 5: Commit**

```bash
git add src/daimon/tray/actions.py tests/test_tray_actions.py
git commit -m "feat(tray): extract a shared, testable ActionRouter (allowlist dispatch)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task 2: Route the AppKit menu through `ActionRouter`

**Files:**
- Modify: `src/daimon/tray/app/statusitem.py` (`_dispatch`)
- Test: existing tray tests stay green (no new test — behavior-preserving refactor verified by the suite).

**Interfaces:**
- Consumes: `ActionRouter`, `ActionHandlers` from Task 1.
- Produces: `statusitem.py` builds an `ActionHandlers` implementation from its existing per-action bodies and calls `ActionRouter(handlers).dispatch(action_id)` from `_dispatch`.

- [ ] **Step 1:** Wrap the existing per-action effect bodies (the code currently inside each `elif` branch of `_dispatch`, lines ~192–304) as methods of a small `_AppKitHandlers` class (or bind them as closures), then replace `_dispatch` with:

```python
    def _dispatch(self, action_id: str) -> None:
        from ...tray.actions import ActionRouter
        res = ActionRouter(self._handlers).dispatch(action_id)
        if not res.ok:
            log_exception(f"action refused: {action_id}: {res.reason}")
```

Keep each effect body byte-for-byte (the dialogs, config writes, `engage_l4` consent flow) — only their *location* moves into handler methods. Build `self._handlers` once in `__init__`.

- [ ] **Step 2: Run the full suite** — `/Users/Ben/.hfenv/bin/pytest -q`. Expected: green (behaviour preserved). Manually confirm the menu still routes on a real Mac later (Phase 6 validation).

- [ ] **Step 3: Commit**

```bash
git add src/daimon/tray/app/statusitem.py
git commit -m "refactor(tray): route the AppKit menu through the shared ActionRouter

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Phase 1 — View model + bridge (pure, headless-testable)

### Task 3: `face/view_model.py` — serialize TrayState to the JSON view contract

**Files:**
- Create: `src/daimon/face/__init__.py` (empty), `src/daimon/face/view_model.py`
- Test: `tests/test_face_view_model.py`

**Interfaces:**
- Consumes: `daimon.tray.state.TrayState`, `daimon.tray.state.ClientStatus`, `daimon.motor.types.Level`.
- Produces: `BRAND` (dict of the locked track), `serialize(state: TrayState) -> dict` with keys `version, permissions{screen_recording,accessibility}, clients[{name,registered}], ceiling{current,settable,l4_active}, overlay_on, brand`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_face_view_model.py
from daimon.face.view_model import serialize, BRAND
from daimon.tray.state import TrayState, ClientStatus
from daimon.motor.types import Level


def _state(**kw):
    base = dict(version="0.1.0", screen_ok=True, accessibility_ok=False,
                clients=(ClientStatus("Claude", True), ClientStatus("Cursor", False)),
                ceiling=Level.INPUT, l4_active=False, overlay_on=True)
    base.update(kw)
    return TrayState(**base)


def test_serialize_shape_and_values():
    v = serialize(_state())
    assert v["version"] == "0.1.0"
    assert v["permissions"] == {"screen_recording": True, "accessibility": False}
    assert v["clients"] == [{"name": "Claude", "registered": True},
                            {"name": "Cursor", "registered": False}]
    assert v["ceiling"]["current"] == "INPUT"
    assert v["ceiling"]["settable"] == ["READ", "NONDESTRUCTIVE", "INPUT", "VALIDATION"]
    assert v["ceiling"]["l4_active"] is False
    assert v["overlay_on"] is True


def test_serialize_carries_locked_brand_track():
    v = serialize(_state())
    assert v["brand"] is BRAND
    assert BRAND["presence"] == "#B66CFF" and BRAND["companion"] == "#E8B23A"
    assert BRAND["finish"] == "indigo" and BRAND["lead"] == "beside" and BRAND["style"] == "organic"


def test_serialize_never_exposes_autonomous_as_settable():
    assert "AUTONOMOUS" not in serialize(_state(ceiling=Level.AUTONOMOUS))["ceiling"]["settable"]


def test_serialize_reports_l4_active():
    assert serialize(_state(l4_active=True))["ceiling"]["l4_active"] is True
```

- [ ] **Step 2: Run — FAIL.** `/Users/Ben/.hfenv/bin/pytest tests/test_face_view_model.py -q`

- [ ] **Step 3: Implement**

```python
# src/daimon/face/view_model.py
"""Pure serializer: the immutable TrayState -> the JSON contract the webview
renders. Presentational only — it carries no secrets and no perception content,
and it exposes the real L0-L4 ceiling (AUTONOMOUS is never 'settable')."""

from __future__ import annotations

from ..tray.state import TrayState

# Locked brand track (the chosen Claude Design "Duo beside" identity).
BRAND = {
    "style": "organic", "lead": "beside", "finish": "indigo",
    "presence": "#B66CFF", "companion": "#E8B23A",
}

# Settable from the UI; AUTONOMOUS (L4) is consent-gated, never here.
_SETTABLE = ["READ", "NONDESTRUCTIVE", "INPUT", "VALIDATION"]


def serialize(state: TrayState) -> dict:
    return {
        "version": state.version,
        "permissions": {
            "screen_recording": bool(state.screen_ok),
            "accessibility": bool(state.accessibility_ok),
        },
        "clients": [{"name": c.name, "registered": bool(c.registered)} for c in state.clients],
        "ceiling": {
            "current": state.ceiling.name,
            "settable": list(_SETTABLE),
            "l4_active": bool(state.l4_active),
        },
        "overlay_on": bool(state.overlay_on),
        "brand": BRAND,
    }
```

- [ ] **Step 4: Run — PASS.** Then full suite.

- [ ] **Step 5: Commit**

```bash
git add src/daimon/face/__init__.py src/daimon/face/view_model.py tests/test_face_view_model.py
git commit -m "feat(face): pure view_model serializer (real L0-L4 ceiling, locked brand)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

### Task 4: `face/bridge.py` — typed JS↔Python API

**Files:**
- Create: `src/daimon/face/bridge.py`
- Test: `tests/test_face_bridge.py`

**Interfaces:**
- Consumes: `ActionRouter` (Task 1), `serialize` (Task 3), a `state_provider: Callable[[], TrayState]`.
- Produces: `FaceBridge(router: ActionRouter, state_provider)` with `get_state() -> dict` (returns `serialize(state_provider())`) and `invoke(action_id: str, args: dict | None = None) -> dict` (returns `{"ok": bool, "reason": str}`). These two methods are the entire `js_api` surface.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_face_bridge.py
from daimon.face.bridge import FaceBridge
from daimon.tray.actions import ActionRouter
from daimon.tray.state import TrayState, ClientStatus
from daimon.motor.types import Level
from test_tray_actions import _Rec  # reuse the recording handlers


def _state():
    return TrayState(version="0.1.0", screen_ok=True, accessibility_ok=True,
                     clients=(ClientStatus("Claude", True),), ceiling=Level.READ,
                     l4_active=False, overlay_on=False)


def _bridge(rec=None):
    rec = rec or _Rec()
    return FaceBridge(ActionRouter(rec), _state), rec


def test_get_state_returns_serialized_view():
    b, _ = _bridge()
    v = b.get_state()
    assert v["ceiling"]["current"] == "READ"
    assert v["brand"]["presence"] == "#B66CFF"


def test_invoke_routes_and_reports_ok():
    b, rec = _bridge()
    assert b.invoke("toggle_overlay") == {"ok": True, "reason": ""}
    assert ("toggle_overlay",) in rec.calls


def test_invoke_rejects_unknown_and_l4_set():
    b, rec = _bridge()
    assert b.invoke("danger")["ok"] is False
    r = b.invoke("set_ceiling:AUTONOMOUS")
    assert r["ok"] is False and "l4" in r["reason"].lower()
    assert rec.calls == []
```

- [ ] **Step 2: Run — FAIL.**

- [ ] **Step 3: Implement**

```python
# src/daimon/face/bridge.py
"""The single typed JS<->Python surface exposed to the webview (pywebview js_api).
Exactly two methods: get_state (read serialized, non-secret view) and invoke
(route a known action_id through the shared ActionRouter). The web layer holds no
authority; this bridge cannot raise the ceiling and never returns secrets."""

from __future__ import annotations

from typing import Callable

from ..tray.state import TrayState
from .bridge_types import BridgeResult  # see note below; or inline dict
from .view_model import serialize


class FaceBridge:
    def __init__(self, router, state_provider: Callable[[], TrayState]) -> None:
        self._router = router
        self._state = state_provider

    def get_state(self) -> dict:
        return serialize(self._state())

    def invoke(self, action_id: str, args: dict | None = None) -> dict:
        res = self._router.dispatch(action_id)
        return {"ok": res.ok, "reason": res.reason}
```

(Drop the `bridge_types` import — return the plain dict inline as shown; the import line is illustrative and must be deleted in the real file.)

- [ ] **Step 4: Run — PASS.** Then full suite. (Note: the test imports `from test_tray_actions import _Rec`; pytest's rootdir puts `tests/` on the path — if collection fails, move `_Rec` into a `tests/conftest.py` fixture and adapt.)

- [ ] **Step 5: Commit**

```bash
git add src/daimon/face/bridge.py tests/test_face_bridge.py
git commit -m "feat(face): FaceBridge — typed get_state/invoke over the ActionRouter

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Phase 2 — Web bundle pipeline (CD → offline dist)

### Task 5: `build/make_face.py` — esbuild the de-playgrounded CD bundle

**Files:**
- Create: `build/make_face.py`, `src/daimon/face/web/src/` (entry + components), `src/daimon/face/web/src/bridge.js`
- Modify: `.gitignore` (ignore `face/web/dist/` except a `.gitkeep`)
- Test: `tests/test_face_bundle.py`

**Interfaces:**
- Produces: `build/make_face.py` runs `npx esbuild` to bundle `src/daimon/face/web/src/panel/index.jsx` (+ overlay, onboarding entries) → `src/daimon/face/web/dist/<surface>/index.html` + `bundle.js`, fully offline (vendored React), CSP `default-src 'self'` injected into each `index.html`.

**Web source (de-playgrounded from the CD project):**
- Copy the CD components into `face/web/src/lib/`: `daimon-icons.jsx` (marks), `daimon-menu.jsx` (panel), and write new `overlay-face.jsx`, `onboarding.jsx`. Remove the tweaks panel, the Babel-CDN `<script>` tags, and `TWEAK_DEFAULTS`; the brand track comes from `get_state().brand`.
- `bridge.js` wraps pywebview's injected API:

```js
// src/daimon/face/web/src/bridge.js
export const bridge = {
  async getState() { return window.pywebview.api.get_state(); },
  async invoke(actionId, args = {}) { return window.pywebview.api.invoke(actionId, args); },
  onState(cb) { window.addEventListener("daimon:state", (e) => cb(e.detail)); },
};
// Python pushes state via window.evaluate_js("window.dispatchEvent(new CustomEvent('daimon:state',{detail:%s}))" % json)
```

- [ ] **Step 1: Write the failing test (bundle smoke)**

```python
# tests/test_face_bundle.py
import subprocess, sys, pathlib, re, pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIST = ROOT / "src/daimon/face/web/dist"


def _build():
    subprocess.run([sys.executable, str(ROOT / "build/make_face.py")], check=True, cwd=ROOT)


@pytest.mark.skipif(not (ROOT / "build/make_face.py").exists(), reason="builder not present yet")
def test_bundle_builds_offline_and_locked():
    _build()
    panel = DIST / "panel" / "index.html"
    assert panel.exists(), "panel bundle missing"
    html = panel.read_text()
    assert "default-src 'self'" in html, "CSP missing"
    # No remote origins anywhere in the dist (offline-only).
    for f in DIST.rglob("*"):
        if f.suffix in {".html", ".js", ".css"}:
            assert not re.search(r"https?://(?!.*'self')", f.read_text()), f"remote URL in {f}"
```

- [ ] **Step 2: Run — FAIL** (builder absent → skip; once builder exists but dist empty → fail). `/Users/Ben/.hfenv/bin/pytest tests/test_face_bundle.py -q`

- [ ] **Step 3: Implement `build/make_face.py`**

```python
# build/make_face.py
"""Build the offline Daimon 'face' web bundle with esbuild (via npx). Bundles each
surface entry (panel/overlay/onboarding) with vendored React — no CDN, no remote.
Injects a strict CSP into each generated index.html. Output: src/daimon/face/web/dist/."""

from __future__ import annotations

import json, shutil, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src/daimon/face/web/src"
DIST = ROOT / "src/daimon/face/web/dist"
SURFACES = ("panel", "overlay", "onboarding")
CSP = "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:;"

_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{csp}">
<style>{css}</style></head><body><div id="root"></div>
<script src="./bundle.js"></script></body></html>"""


def _npx_esbuild(entry: Path, outfile: Path) -> None:
    subprocess.run(["npx", "--yes", "esbuild", str(entry), "--bundle",
                    "--format=iife", "--loader:.jsx=jsx", "--jsx=automatic",
                    f"--outfile={outfile}"], check=True, cwd=ROOT)


def main() -> int:
    if shutil.which("npx") is None:
        print("ERROR: npx (Node) is required to build the face bundle.", file=sys.stderr)
        return 2
    DIST.mkdir(parents=True, exist_ok=True)
    base_css = (SRC / "base.css").read_text() if (SRC / "base.css").exists() else ""
    for s in SURFACES:
        entry = SRC / s / "index.jsx"
        if not entry.exists():
            continue
        out_dir = DIST / s
        out_dir.mkdir(parents=True, exist_ok=True)
        _npx_esbuild(entry, out_dir / "bundle.js")
        (out_dir / "index.html").write_text(_HTML.format(csp=CSP, css=base_css))
    print(f"face bundle -> {DIST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Create minimal `src/daimon/face/web/src/panel/index.jsx` that renders the de-playgrounded `DaimonMenu` bound to `bridge.getState()` (and `overlay/index.jsx`, `onboarding/index.jsx` stubs that render their root components). Vendor React by adding it to `package.json` devDeps OR let esbuild resolve a local `node_modules/react` (run `npm i react react-dom` once in `face/web/`). Document the one-time `npm i` in `build/make_face.py`'s header.

- [ ] **Step 4: Run — PASS** (`npx esbuild` builds; CSP present; no remote URLs). Then full suite.

- [ ] **Step 5: Commit**

```bash
git add build/make_face.py src/daimon/face/web/src .gitignore tests/test_face_bundle.py
git commit -m "build(face): offline esbuild bundle pipeline (vendored React, locked CSP)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Phase 3 — Panel surface (pywebview, native traits) — needs pywebview + real Mac

> Add pywebview as a guarded dependency first: in `pyproject.toml` add `"pywebview>=5.0; sys_platform == 'darwin'"` and `"pywebview>=5.0; sys_platform == 'win32'"`. `face/host.py` lazy-imports `webview` inside functions so unit tests import the module without the dep.

### Task 6: `face/host.py` — window lifecycle (with a fake webview seam)

**Files:**
- Create: `src/daimon/face/host.py`
- Test: `tests/test_face_host.py`

**Interfaces:**
- Produces: `FaceHost(bridge: FaceBridge, webview_module=None)` with `open_panel()`, `open_overlay()`, `open_onboarding()`, `push_state()`. `webview_module` defaults to a lazy `import webview`; tests inject a fake recording module. Each `open_*` creates a window pointing at the built `dist/<surface>/index.html`, exposing `bridge` as `js_api`, with the per-surface traits requested from the platform adapter.

- [ ] **Step 1: Write the failing test (fake webview module)**

```python
# tests/test_face_host.py
from daimon.face.host import FaceHost


class _FakeWindow:
    def __init__(self): self.evaluated = []
    def evaluate_js(self, js): self.evaluated.append(js)


class _FakeWebview:
    def __init__(self): self.created = []
    def create_window(self, title, url, js_api=None, frameless=False, **kw):
        w = _FakeWindow(); self.created.append({"title": title, "url": url, "js_api": js_api,
                                                "frameless": frameless, "kw": kw}); return w


class _FakeBridge:
    def get_state(self): return {"ok": 1}
    def invoke(self, a, args=None): return {"ok": True}


def test_open_panel_creates_frameless_window_with_bridge():
    fw = _FakeWebview()
    host = FaceHost(_FakeBridge(), webview_module=fw)
    host.open_panel()
    w = fw.created[-1]
    assert w["frameless"] is True
    assert w["js_api"].__class__.__name__ == "_FakeBridge"
    assert w["url"].endswith("panel/index.html")


def test_push_state_evaluates_state_event():
    fw = _FakeWebview()
    host = FaceHost(_FakeBridge(), webview_module=fw)
    host.open_panel()
    host.push_state()
    assert any("daimon:state" in js for js in host._windows["panel"].evaluated)
```

- [ ] **Step 2: Run — FAIL.**

- [ ] **Step 3: Implement** `FaceHost` resolving `dist/<surface>/index.html` via `importlib.resources`/path, creating frameless windows for panel+overlay and a normal one for onboarding, storing them in `self._windows`, and `push_state()` calling `evaluate_js` with a `daimon:state` CustomEvent carrying `json.dumps(bridge.get_state())`. Lazy `import webview` only when `webview_module is None` AND an `open_*` is actually called.

- [ ] **Step 4: Run — PASS.** Full suite.

- [ ] **Step 5: Commit** (`feat(face): FaceHost window lifecycle + state push (fake-webview tested)`).

### Task 7: macOS platform adapter — vibrancy, anchor, capture-exclusion

**Files:**
- Create: `src/daimon/face/platform/__init__.py`, `src/daimon/face/platform/macos.py`
- Test: `tests/test_face_platform.py` (pure selector test; native calls are real-Mac manual)

**Interfaces:**
- Produces: `get_adapter()` returns the macOS adapter on darwin, the Windows scaffold on win32; adapter has `anchor_under_statusitem(window, statusitem)`, `apply_vibrancy(window, dark: bool)`, `exclude_from_capture(window)`. On macOS these use the `NSWindow` behind the pywebview window (via `window.gui` / native handle): `NSVisualEffectView` as `contentView` backing, `setSharingType_(NSWindowSharingNone)`, and position from the `NSStatusItem.button.window` frame.

- [ ] **Step 1: Test the selector only** (native bodies are validated on a real Mac):

```python
# tests/test_face_platform.py
import sys
from daimon.face.platform import get_adapter

def test_selector_returns_an_adapter_with_the_contract():
    a = get_adapter()
    for name in ("anchor_under_statusitem", "apply_vibrancy", "exclude_from_capture"):
        assert callable(getattr(a, name))
```

- [ ] **Step 2: Run — FAIL.** **Step 3: Implement** the selector + macOS adapter (pyobjc bodies) + a Windows scaffold raising `NotImplementedError` with a TODO (acrylic/Mica + `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` + tray geometry). **Step 4:** selector test passes on macOS; native behavior is Phase 6 manual. **Step 5: Commit.**

### Task 8: Wire the status-item click to open the panel

**Files:** Modify `src/daimon/tray/app/statusitem.py` (status-item action), reuse `FaceHost`.
- [ ] Build a `FaceHost(FaceBridge(ActionRouter(self._handlers), gather))` once; on the status-item button click, `host.open_panel()` (anchored, vibrant, dismiss-on-blur), and call `host.push_state()` whenever tray state changes. Keep the native `NSMenu` reachable (e.g. right-click / control-click) as the fallback. Verify on a real Mac (Phase 6). Commit (`feat(face): open the webview panel from the menu-bar icon`).

---

## Phase 4 — Overlay face (wraps the existing engine)

### Task 9: Overlay surface composited over the `overlay_*` engine

**Files:** Create `src/daimon/face/web/src/overlay/`, extend `face/host.py` (`open_overlay`), reuse the macOS adapter's `exclude_from_capture`.

**Interfaces:** Consumes the existing overlay draw transport (unchanged). Produces a transparent, click-through-except-interactive, **capture-excluded**, always-on-top, per-display webview "face" composited above the existing `overlay_*` canvas. The MCP `overlay_*` tool contract is untouched.

- [ ] **Step 1: Test (host wiring + exclusion call)** — assert `open_overlay()` creates a `frameless`, `transparent`/`on_top` window and calls `adapter.exclude_from_capture(window)` (use the fake webview + a fake adapter recording the call). **Step 2:** FAIL. **Step 3:** implement `open_overlay()` requesting transparent/on-top/frameless and invoking `exclude_from_capture`. **Step 4:** PASS + full suite. **Step 5:** Commit (`feat(face): overlay companion surface, capture-excluded, wrapping overlay_*`).
- [ ] **Real-Mac validation (Phase 6):** screenshot the desktop and confirm the overlay face is ABSENT from the capture (exclusion holds), while `overlay_*` highlights still render.

---

## Phase 5 — Onboarding surface

### Task 10: Onboarding window (first-run journey)

**Files:** Create `src/daimon/face/web/src/onboarding/`, extend `face/host.py` (`open_onboarding`), a first-run trigger.

**Interfaces:** Produces a normal frameless onboarding window: welcome → register clients (`install_all` / per-client) → permissions walkthrough (grant + the denied-permission deep-link state) → ceiling explainer (real L0–L4, L4 consent). All actions go through the same bridge.

- [ ] **Step 1: Test** — `open_onboarding()` creates a window pointing at `onboarding/index.html` with the bridge as `js_api` (fake webview). **Step 2:** FAIL. **Step 3:** implement. **Step 4:** PASS + full suite. **Step 5:** Commit (`feat(face): onboarding surface bound to the bridge`).
- [ ] Wire first-run detection (reuse the existing onboarding trigger that opens today's setup window) to `host.open_onboarding()`; keep the old setup window behind a flag for one release. Commit.

---

## Phase 6 — Real-machine validation (Ben-operated; not headless)

- [ ] `npm i react react-dom` in `src/daimon/face/web/`, then `python build/make_face.py` → `dist/` populated.
- [ ] `pip install 'pywebview>=5.0'` in the build env; launch the tray; click the menu-bar glyph → the **panel** opens anchored under the glyph, vibrant, dismisses on blur; toggles/ceiling/permissions reflect and drive real state (verify a `set_ceiling:INPUT` actually moves the Hands ceiling; `engage_l4` still shows the native consent dialog).
- [ ] **Overlay capture-exclusion:** enable the overlay, `vue_snapshot` the desktop → the overlay face must be ABSENT from the capture; `overlay_*` highlights still draw.
- [ ] **Onboarding:** fresh profile → onboarding opens, register + grant walkthrough works, deep-links land in the right System Settings panes.
- [ ] Windows: repeat panel/onboarding with WebView2 + acrylic + tray-anchor + `WDA_EXCLUDEFROMCAPTURE` (after the Windows adapter is implemented on `feat/windows-port`/post-merge).

## Final verification

- [ ] `/Users/Ben/.hfenv/bin/pytest -q` green (≥ 405 + the new face/router tests).
- [ ] `face/web/dist` builds offline; CSP present; no remote URLs (grep gate green).
- [ ] No secret/perception field crosses the bridge (`view_model.serialize` exposes only version/permissions/clients/ceiling/overlay/brand).
- [ ] `set_ceiling:AUTONOMOUS` refused at both `ActionRouter` and bridge; L4 only via `engage_l4`.
- [ ] Overlay window verified capture-excluded on a real Mac.

## Out of scope (YAGNI)

- Replacing the `overlay_*` draw engine (wrapped, untouched).
- A production tweaks panel (track locked).
- Linux/GTK UI.
- Auto-syncing CD → `face/web/src` (manual re-sync via DesignSync for now).
