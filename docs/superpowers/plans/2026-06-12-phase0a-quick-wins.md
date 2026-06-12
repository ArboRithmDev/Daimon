# Phase 0a — Quick Wins Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make Daimon sustainable in a real driving loop — bound `touche_tree` (token cost ÷3-5), target windows reliably, capture regions, and add the two P0 input unblockers (double-click, keyboard events).

**Architecture:** Extend `capture/accessibility.py` (parametrised tree), `senses/touche.py` + `senses/vue.py` (new params), `motor/` (new gestures via the existing guard→organ→actuator pipeline). Pure tree-shaping logic is unit-tested with mock node dicts; macOS-touching code (capture, AX, CGEvent) sits behind the existing lazy-import pattern and is validated by smoke.

**Tech Stack:** Python 3.12, pyobjc (Quartz/ApplicationServices/AppKit), FastMCP, pytest.

---

## File structure

| File | Change |
|------|--------|
| `src/daimon/capture/treeshape.py` | NEW — pure tree-shaping: depth cap, role filter, prune_empty, summary, value truncation |
| `src/daimon/capture/accessibility.py` | extend `snapshot_tree(...)` with params + window targeting + fallback; add `window_element` resolver |
| `src/daimon/senses/touche.py` | `touche_tree` exposes max_depth/root/roles/prune_empty/summary/window |
| `src/daimon/capture/screen.py` | `capture_display` gains `region`; lower default `max_width` |
| `src/daimon/senses/vue.py` | `vue_snapshot` exposes `region`; default max_width 720 |
| `src/daimon/motor/actions.py` | register `main_activate` (L1) |
| `src/daimon/motor/actuator.py` | `_click` honours `button`/`count`/`modifiers`; add `_key`, `_hover`, `_activate` |
| `src/daimon/motor/keys.py` | NEW — pure key-name → macOS keycode + modifier-flag mapping |
| `src/daimon/server.py` | new tool params + `main_activate`, `main_key`; double-click param |
| `tests/test_*` | per task |

---

## Task 1: Pure tree-shaping module

**Files:** Create `src/daimon/capture/treeshape.py`, `tests/test_treeshape.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_treeshape.py
from daimon.capture.treeshape import shape_tree, to_summary_lines


def _tree():
    return {
        "role": "AXWindow", "title": "Win", "value": None,
        "position": {"x": 0, "y": 0}, "size": {"width": 100, "height": 50},
        "children": [
            {"role": "AXGroup", "title": None, "value": None, "children": [
                {"role": "AXButton", "title": "OK", "value": None},
            ]},
            {"role": "AXUnknown", "title": None, "value": None, "description": None},
            {"role": "AXTextField", "title": None, "value": "x" * 500},
        ],
    }


def test_max_depth_caps_tree():
    out = shape_tree(_tree(), max_depth=1)
    # depth 0 = window, depth 1 = its children, no grandchildren
    grp = out["children"][0]
    assert "children" not in grp or grp.get("children_truncated")


def test_prune_empty_drops_decorative_nodes():
    out = shape_tree(_tree(), prune_empty=True)
    roles = [c["role"] for c in out["children"]]
    assert "AXUnknown" not in roles  # no title/value/children → pruned
    assert "AXButton" in [d["role"] for d in out["children"][0]["children"]]


def test_roles_filter_keeps_only_requested_plus_ancestors():
    out = shape_tree(_tree(), roles=["AXButton"])
    # the button is kept, and its ancestor group is kept for structure
    grp = next(c for c in out["children"] if c["role"] == "AXGroup")
    assert grp["children"][0]["role"] == "AXButton"
    assert all(c["role"] != "AXTextField" for c in out["children"])


def test_value_is_truncated():
    out = shape_tree(_tree(), max_value_chars=10)
    tf = next(c for c in out["children"] if c["role"] == "AXTextField")
    assert len(tf["value"]) <= 11  # 10 + ellipsis marker


def test_summary_one_line_per_node():
    lines = to_summary_lines(_tree())
    assert any(line.strip().startswith("AXWindow") and "Win" in line for line in lines)
    assert any("AXButton" in line and "OK" in line for line in lines)
    # indentation reflects depth
    assert lines[0].startswith("AXWindow") or not lines[0].startswith(" ")
```

- [ ] **Step 2: Run, expect FAIL** — `PYTHONPATH=src python -m pytest tests/test_treeshape.py -v` → ModuleNotFoundError.

- [ ] **Step 3: Implement**

```python
# src/daimon/capture/treeshape.py
"""Pure tree-shaping for touche_tree — no macOS imports.

Operates on the plain node dicts produced by the accessibility backend:
{role, subrole, title, value, description, position, size, children?}.
Bounds the tree (depth/roles/prune/value-length) and offers a compact
one-line-per-node summary. Keeping this pure makes the token-control logic
fully unit-testable.
"""

from __future__ import annotations

_ELLIPSIS = "…"


def _has_signal(node: dict) -> bool:
    """A node is meaningful if it carries a title/value/description or kids."""
    return bool(
        node.get("title") or node.get("value") or node.get("description")
        or node.get("children")
    )


def _truncate(value, max_value_chars: int):
    if isinstance(value, str) and max_value_chars and len(value) > max_value_chars:
        return value[:max_value_chars] + _ELLIPSIS
    return value


def shape_tree(
    node: dict,
    *,
    max_depth: int = 4,
    roles: list[str] | None = None,
    prune_empty: bool = True,
    max_value_chars: int = 200,
    _depth: int = 0,
) -> dict:
    """Return a bounded copy of `node`. Roots are always kept."""
    shaped = {k: v for k, v in node.items() if k != "children"}
    if "value" in shaped:
        shaped["value"] = _truncate(shaped["value"], max_value_chars)

    children = node.get("children") or []
    if _depth >= max_depth:
        if children:
            shaped["children_truncated"] = True
        return shaped

    kept = []
    for child in children:
        sc = shape_tree(
            child, max_depth=max_depth, roles=roles,
            prune_empty=prune_empty, max_value_chars=max_value_chars, _depth=_depth + 1,
        )
        if roles is not None:
            # keep if the subtree contains a requested role (self or descendants)
            if not _subtree_has_role(sc, roles):
                continue
        if prune_empty and not _has_signal(sc) and sc.get("role") in (None, "AXUnknown", "AXGroup"):
            continue
        kept.append(sc)
    if kept:
        shaped["children"] = kept
    return shaped


def _subtree_has_role(node: dict, roles: list[str]) -> bool:
    if node.get("role") in roles:
        return True
    return any(_subtree_has_role(c, roles) for c in node.get("children") or [])


def to_summary_lines(node: dict, *, _depth: int = 0) -> list[str]:
    """Compact one-line-per-node rendering: `<indent>ROLE "title" [x,y w×h]`."""
    indent = "  " * _depth
    title = node.get("title") or node.get("value") or node.get("description") or ""
    title = f' "{title}"' if title else ""
    pos, size = node.get("position"), node.get("size")
    geom = ""
    if pos and size:
        geom = f' [{pos["x"]},{pos["y"]} {size["width"]}×{size["height"]}]'
    lines = [f"{indent}{node.get('role')}{title}{geom}".rstrip()]
    for child in node.get("children") or []:
        lines.extend(to_summary_lines(child, _depth=_depth + 1))
    return lines
```

- [ ] **Step 4: Run, expect PASS** — 5 passed.

- [ ] **Step 5: Commit** — `git add src/daimon/capture/treeshape.py tests/test_treeshape.py && git commit -m "feat(touche): pure bounded tree-shaping (depth/roles/prune/summary)"`

---

## Task 2: Parametrise accessibility.snapshot_tree + window targeting

**Files:** Modify `src/daimon/capture/accessibility.py`, Test `tests/test_accessibility_shape.py`

- [ ] **Step 1: Write the failing test** (tests the pure integration: snapshot_tree delegates shaping; window resolver is mocked)

```python
# tests/test_accessibility_shape.py
from daimon.capture import accessibility as ax


def test_snapshot_tree_applies_shaping(monkeypatch):
    raw = {"role": "AXWindow", "title": "W", "children": [
        {"role": "AXUnknown", "title": None, "value": None},
        {"role": "AXButton", "title": "Go"},
    ]}
    monkeypatch.setattr(ax, "_raw_tree", lambda root, max_nodes: raw)
    monkeypatch.setattr(ax, "_resolve_root", lambda window, root_point: object())
    out = ax.snapshot_tree(prune_empty=True)
    roles = [c["role"] for c in out["children"]]
    assert "AXUnknown" not in roles and "AXButton" in roles


def test_snapshot_tree_summary_returns_text(monkeypatch):
    raw = {"role": "AXWindow", "title": "W", "children": [{"role": "AXButton", "title": "Go"}]}
    monkeypatch.setattr(ax, "_raw_tree", lambda root, max_nodes: raw)
    monkeypatch.setattr(ax, "_resolve_root", lambda window, root_point: object())
    out = ax.snapshot_tree(summary=True)
    assert isinstance(out, dict) and "summary" in out
    assert "AXButton" in out["summary"]
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — refactor `accessibility.py`. Keep `node_from_element`, `element_at`, `is_trusted`, `_copy_attr`, `_point_size`, `_stringify`. Replace `_walk`/`snapshot_tree` with a raw-walker plus a shaping wrapper, and add root resolution:

```python
# add near top
from .treeshape import shape_tree, to_summary_lines

_DEFAULT_MAX_DEPTH = 4


def _raw_tree(root, max_nodes: int) -> dict:
    """Walk the AX tree into plain dicts, capped only by node count (depth/role
    shaping happens later in treeshape, which is pure and testable)."""
    counter = [0]

    def walk(element) -> dict:
        from ApplicationServices import kAXChildrenAttribute
        node = node_from_element(element)
        counter[0] += 1
        if counter[0] >= max_nodes:
            node["children_truncated"] = True
            return node
        children = _copy_attr(element, kAXChildrenAttribute) or []
        kids = []
        for child in children:
            if counter[0] >= max_nodes:
                node["children_truncated"] = True
                break
            kids.append(walk(child))
        if kids:
            node["children"] = kids
        return node

    return walk(root)


def _window_element(window: dict):
    """Resolve an AX application element by {pid|bundle|title}."""
    from AppKit import NSWorkspace
    from ApplicationServices import AXUIElementCreateApplication, kAXFocusedWindowAttribute

    pid = window.get("pid")
    if pid is None:
        apps = NSWorkspace.sharedWorkspace().runningApplications()
        for app in apps:
            if window.get("bundle") and app.bundleIdentifier() == window["bundle"]:
                pid = int(app.processIdentifier()); break
            if window.get("title") and app.localizedName() == window["title"]:
                pid = int(app.processIdentifier()); break
    if pid is None:
        raise RuntimeError(f"No app matching {window}")
    app_el = AXUIElementCreateApplication(pid)
    win = _copy_attr(app_el, kAXFocusedWindowAttribute)
    return win if win is not None else app_el


def _resolve_root(window, root_point):
    from ApplicationServices import (
        AXUIElementCopyElementAtPosition, AXUIElementCreateSystemWide,
        AXUIElementCreateApplication, kAXFocusedWindowAttribute,
    )
    if root_point is not None:
        system = AXUIElementCreateSystemWide()
        err, el = AXUIElementCopyElementAtPosition(
            system, float(root_point["x"]), float(root_point["y"]), None)
        if err != 0 or el is None:
            raise RuntimeError(f"No element at {root_point}")
        return el
    if window is not None:
        return _window_element(window)
    # frontmost focused window, with fallback to the app element
    pid = _frontmost_pid()
    if pid is None:
        raise RuntimeError("No frontmost application.")
    app_el = AXUIElementCreateApplication(pid)
    win = _copy_attr(app_el, kAXFocusedWindowAttribute)
    return win if win is not None else app_el


def snapshot_tree(
    *,
    max_depth: int = _DEFAULT_MAX_DEPTH,
    root: dict | None = None,
    roles: list[str] | None = None,
    prune_empty: bool = True,
    summary: bool = False,
    window: dict | None = None,
    max_nodes: int = 600,
    max_value_chars: int = 200,
) -> dict:
    """Touché passif, bounded. `root`={x,y} dumps a subtree; `window`=
    {pid|bundle|title} targets a specific app instead of the frontmost."""
    root_el = _resolve_root(window, root)
    raw = _raw_tree(root_el, max_nodes)
    shaped = shape_tree(
        raw, max_depth=max_depth, roles=roles,
        prune_empty=prune_empty, max_value_chars=max_value_chars,
    )
    if summary:
        return {"summary": "\n".join(to_summary_lines(shaped))}
    return shaped
```

Remove the now-unused `_walk` and old `snapshot_tree` body and the `_MAX_DEPTH` constant (keep `_MAX_NODES` use via `max_nodes` default).

- [ ] **Step 4: Run, expect PASS** (2 passed). Also `PYTHONPATH=src python -c "import daimon.capture.accessibility"` imports clean.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(touche): bounded snapshot_tree with window targeting + subtree root"`

---

## Task 3: Expose bounded params on the touche_tree MCP tool

**Files:** Modify `src/daimon/senses/touche.py`, Test `tests/test_touche_params.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_touche_params.py
import asyncio
from daimon.config import ExclusionConfig
from daimon.exclusions import ExclusionFilter
from daimon.senses.touche import Touche
from mcp.server.fastmcp import FastMCP


def _tool(mcp, name):
    return asyncio.run(mcp.call_tool(name, {}))


def test_touche_tree_accepts_bounding_params(monkeypatch):
    import daimon.capture.accessibility as ax
    captured = {}
    monkeypatch.setattr(ax, "is_trusted", lambda: True)
    def fake_snapshot(**kw):
        captured.update(kw); return {"role": "AXWindow"}
    monkeypatch.setattr(ax, "snapshot_tree", fake_snapshot)

    mcp = FastMCP("t")
    Touche(ExclusionFilter(ExclusionConfig())).register(mcp)
    asyncio.run(mcp.call_tool("touche_tree", {"max_depth": 2, "summary": True}))
    assert captured["max_depth"] == 2
    assert captured["summary"] is True
```

- [ ] **Step 2: Run, expect FAIL** (signature rejects kwargs).

- [ ] **Step 3: Implement** — update `touche_tree` in `senses/touche.py`:

```python
        @mcp.tool(
            name="touche_tree",
            description=(
                "Touché passif: bounded accessibility tree. Defaults are bounded "
                "for cost — pass a bigger max_depth or full=structure only when "
                "needed. `root={x,y}` dumps just the subtree under a point. "
                "`window={pid|bundle|title}` targets a specific app instead of the "
                "frontmost (fixes null-root when focus moves). `roles=[...]` keeps "
                "only those roles. `summary=true` returns a compact one-line-per-node "
                "text. Read-only."
            ),
        )
        def touche_tree(
            max_depth: int = 4,
            root: dict | None = None,
            roles: list[str] | None = None,
            prune_empty: bool = True,
            summary: bool = False,
            window: dict | None = None,
        ) -> dict:
            if not ax.is_trusted():
                return {"error": "accessibility_permission_denied", "hint": _PERMISSION_HINT}
            tree = ax.snapshot_tree(
                max_depth=max_depth, root=root, roles=roles,
                prune_empty=prune_empty, summary=summary, window=window,
            )
            if summary:
                return tree  # already {"summary": "..."} — no node redaction needed
            return self._exclusions.redact_nodes([tree])[0]
```

- [ ] **Step 4: Run, expect PASS.**

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(touche): expose bounded tree params on the MCP tool"`

---

## Task 4: Region capture + lower default for vue_snapshot

**Files:** Modify `src/daimon/capture/screen.py`, `src/daimon/senses/vue.py`, Test `tests/test_vue_region.py`

- [ ] **Step 1: Write the failing test** (pure crop logic extracted so it is testable without a display)

```python
# tests/test_vue_region.py
from daimon.capture.screen import crop_region


class _Img:
    def __init__(self, w, h): self.width, self.height = w, h; self.box = None
    def crop(self, box): self.box = box; return self


def test_crop_region_clamps_to_bounds():
    img = _Img(1000, 800)
    out = crop_region(img, {"x": 100, "y": 50, "width": 5000, "height": 5000})
    assert out.box == (100, 50, 1000, 800)  # clamped to image bounds


def test_crop_region_none_is_identity():
    img = _Img(10, 10)
    assert crop_region(img, None) is img
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — in `screen.py` add the pure helper and a default change:

```python
def crop_region(image, region: dict | None):
    """Crop a PIL image to {x,y,width,height}, clamped to the image. Pure."""
    if not region:
        return image
    x = max(0, int(region["x"])); y = max(0, int(region["y"]))
    right = min(image.width, x + int(region["width"]))
    bottom = min(image.height, y + int(region["height"]))
    return image.crop((x, y, right, bottom))
```

And give `capture_display` a `region` param applied before downscale, and lower the default:

```python
def capture_display(display_index: int = 0, max_width: int | None = 720,
                    region: dict | None = None) -> Frame:
    ...
    img = _cgimage_to_pil(image_ref)
    img = crop_region(img, region)
    if max_width and img.width > max_width:
        ...
```

(Keep `capture_main_display`'s default consistent or leave as-is — only the tool default matters.)

Then in `senses/vue.py`, update `vue_snapshot`:

```python
        def vue_snapshot(display: int = 0, max_width: int = 720,
                         region: dict | None = None) -> MCPImage:
            frame = screen.capture_display(display_index=display, max_width=max_width, region=region)
            ...
```

(Update the tool description to mention `region={x,y,width,height}` and the lower default.)

- [ ] **Step 4: Run, expect PASS.**

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(vue): region capture + lower default max_width (720)"`

---

## Task 5: Pure key mapping module

**Files:** Create `src/daimon/motor/keys.py`, Test `tests/test_motor_keys.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_motor_keys.py
import pytest
from daimon.motor.keys import keycode_for, modifier_mask, KEYCODES


def test_known_keys_map_to_codes():
    for name in ["return", "tab", "escape", "left", "a", "f5"]:
        assert isinstance(keycode_for(name), int)


def test_key_lookup_is_case_insensitive():
    assert keycode_for("Return") == keycode_for("return")


def test_unknown_key_raises():
    with pytest.raises(KeyError):
        keycode_for("nope-key")


def test_modifier_mask_combines():
    assert modifier_mask(["cmd", "shift"]) == modifier_mask(["shift", "cmd"])
    assert modifier_mask([]) == 0
    assert modifier_mask(["cmd"]) != 0
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement** — `src/daimon/motor/keys.py` (pure constants; macOS virtual keycodes):

```python
"""Key-name → macOS virtual keycode + modifier flag mapping. Pure (no imports
of pyobjc); the numeric constants mirror Carbon/CGEvent values so the actuator
can build keyboard events without a lookup table of its own."""

from __future__ import annotations

# Carbon virtual keycodes (kVK_*) for the keys an agent commonly needs.
KEYCODES: dict[str, int] = {
    "return": 36, "enter": 36, "tab": 48, "space": 49, "delete": 51,
    "escape": 27, "esc": 27, "left": 123, "right": 124, "down": 125, "up": 126,
    "home": 115, "end": 119, "pageup": 116, "pagedown": 121, "forwarddelete": 117,
    "f1": 122, "f2": 120, "f3": 99, "f4": 118, "f5": 96, "f6": 97, "f7": 98,
    "f8": 100, "f9": 101, "f10": 109, "f11": 103, "f12": 111,
    "a": 0, "s": 1, "d": 2, "f": 3, "h": 4, "g": 5, "z": 6, "x": 7, "c": 8,
    "v": 9, "b": 11, "q": 12, "w": 13, "e": 14, "r": 15, "y": 16, "t": 17,
    "o": 31, "u": 32, "i": 34, "p": 35, "l": 37, "j": 38, "k": 40, "n": 45, "m": 46,
    "1": 18, "2": 19, "3": 20, "4": 21, "5": 23, "6": 22, "7": 26, "8": 28,
    "9": 25, "0": 29,
}

# CGEventFlags bit masks (mirror Quartz.kCGEventFlagMaskCommand etc.).
_MOD_FLAGS = {
    "cmd": 1 << 20, "command": 1 << 20,
    "shift": 1 << 17,
    "opt": 1 << 19, "option": 1 << 19, "alt": 1 << 19,
    "ctrl": 1 << 18, "control": 1 << 18,
}


def keycode_for(name: str) -> int:
    return KEYCODES[name.strip().lower()]


def modifier_mask(modifiers: list[str]) -> int:
    mask = 0
    for m in modifiers or []:
        mask |= _MOD_FLAGS[m.strip().lower()]
    return mask
```

- [ ] **Step 4: Run, expect PASS.**

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(motor): pure key-name → keycode/modifier mapping"`

---

## Task 6: main_key + double-click + activate — actions, actuator, classifier

**Files:** Modify `src/daimon/motor/actions.py`, `src/daimon/motor/actuator.py`, `src/daimon/motor/reversibility.py`, Test `tests/test_motor_keys_actions.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_motor_keys_actions.py
from daimon.motor.actions import ACTIONS, level_for
from daimon.motor.actuator import FakeActuator
from daimon.motor.reversibility import classify
from daimon.motor.types import Declaration, Level, MotorAction, Target


def test_new_verbs_registered():
    assert level_for("main_key") == Level.INPUT
    assert level_for("main_activate") == Level.NONDESTRUCTIVE
    assert level_for("main_hover") == Level.NONDESTRUCTIVE


def _key(combo_keys, params):
    return MotorAction(name="key", level=Level.INPUT, target=Target(),
                       declaration=Declaration(reversible=True, intent="x"), params=params)


def test_dangerous_key_combo_classified_irreversible():
    a = _key("cmd+delete", {"key": "delete", "modifiers": ["cmd"], "keystr": "cmd+delete"})
    assert classify(a).irreversible


def test_plain_key_is_reversible():
    a = _key("tab", {"key": "tab", "modifiers": [], "keystr": "tab"})
    assert not classify(a).irreversible


def test_fake_actuator_runs_key_and_activate():
    act = FakeActuator()
    act.execute(MotorAction(name="key", level=Level.INPUT, target=Target(),
                            declaration=Declaration(reversible=True, intent="x"),
                            params={"key": "return", "modifiers": []}))
    act.execute(MotorAction(name="activate", level=Level.NONDESTRUCTIVE, target=Target(),
                            declaration=Declaration(reversible=True, intent="x"),
                            params={"bundle": "com.apple.TextEdit"}))
    assert [a.name for a in act.executed] == ["key", "activate"]
```

- [ ] **Step 2: Run, expect FAIL.**

- [ ] **Step 3: Implement**

In `actions.py` add to `ACTIONS`:
```python
    "main_key": ActionDef("main_key", Level.INPUT, "discrete key / chord"),
    "main_hover": ActionDef("main_hover", Level.NONDESTRUCTIVE, "move pointer only"),
    "main_activate": ActionDef("main_activate", Level.NONDESTRUCTIVE, "bring app/window frontmost"),
```

In `reversibility.py`, make the key-combo check also read a `keystr` param (the human-readable combo) in addition to `keys`:
```python
    keys = action.params.get("keys") or action.params.get("keystr")
```
(the existing `_DANGER_KEYS` regex already matches `cmd+delete`).

In `actuator.py` `MacOSActuator.execute` handler map add `"key"`, `"hover"`, `"activate"`; add the methods:
```python
    def _key(self, action):
        import Quartz
        from .keys import keycode_for, modifier_mask
        code = keycode_for(action.params["key"])
        flags = modifier_mask(action.params.get("modifiers", []))
        count = int(action.params.get("count", 1))
        for _ in range(count):
            for is_down in (True, False):
                ev = Quartz.CGEventCreateKeyboardEvent(None, code, is_down)
                if flags:
                    Quartz.CGEventSetFlags(ev, flags)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)

    def _hover(self, action):
        import Quartz
        x = action.params.get("x", action.target.x); y = action.params.get("y", action.target.y)
        ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, (x, y), 0)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)

    def _activate(self, action):
        from AppKit import NSWorkspace, NSRunningApplication
        p = action.params
        for app in NSWorkspace.sharedWorkspace().runningApplications():
            if (p.get("bundle") and app.bundleIdentifier() == p["bundle"]) or \
               (p.get("title") and app.localizedName() == p["title"]) or \
               (p.get("pid") and int(app.processIdentifier()) == p["pid"]):
                app.activateWithOptions_(1 << 1)  # NSApplicationActivateIgnoringOtherApps
                return
        raise RuntimeError(f"No app matching {p}")
```

Extend `_click` to honour `button`/`count`/`modifiers`:
```python
    def _click(self, action):
        import Quartz
        from .keys import modifier_mask
        x = action.params.get("x", action.target.x); y = action.params.get("y", action.target.y)
        button = action.params.get("button", "left")
        count = int(action.params.get("count", 1))
        flags = modifier_mask(action.params.get("modifiers", []))
        down_t, up_t, btn = {
            "left": (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp, Quartz.kCGMouseButtonLeft),
            "right": (Quartz.kCGEventRightMouseDown, Quartz.kCGEventRightMouseUp, Quartz.kCGMouseButtonRight),
            "middle": (Quartz.kCGEventOtherMouseDown, Quartz.kCGEventOtherMouseUp, Quartz.kCGMouseButtonCenter),
        }[button]
        for i in range(count):
            for et in (down_t, up_t):
                ev = Quartz.CGEventCreateMouseEvent(None, et, (x, y), btn)
                if flags:
                    Quartz.CGEventSetFlags(ev, flags)
                if count > 1:
                    Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGMouseEventClickState, i + 1)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
```

- [ ] **Step 4: Run, expect PASS.** Also `PYTHONPATH=src python -c "import daimon.motor.actuator"`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(motor): main_key, main_hover, main_activate; click button/count/modifiers"`

---

## Task 7: Register new motor tools + tool-registration test (F2)

**Files:** Modify `src/daimon/server.py`, Test `tests/test_server_tools.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_server_tools.py
import asyncio
from daimon.server import build_server


def test_server_exposes_full_toolset():
    names = {t.name for t in asyncio.run(build_server().list_tools())}
    expected = {
        "vue_displays", "vue_snapshot", "touche_tree", "touche_probe",
        "main_click", "main_type", "main_press", "main_navigate",
        "main_key", "main_hover", "main_activate",
    }
    assert expected <= names
```

- [ ] **Step 2: Run, expect FAIL** (main_key/hover/activate not registered).

- [ ] **Step 3: Implement** — in `server.py` `_register_motor`, give `main_click` the new params and add three tools:

```python
    def main_click(x: int, y: int, intent: str, reversible: bool = True,
                   button: str = "left", count: int = 1, modifiers: list[str] | None = None,
                   role: str = "", label: str = "") -> dict:
        return organ.act(MotorAction(
            name="click", level=level_for("main_click"),
            target=_target(x, y, role or None, label or None),
            declaration=Declaration(reversible=reversible, intent=intent),
            params={"x": x, "y": y, "button": button, "count": count,
                    "modifiers": modifiers or []},
        ))

    @mcp.tool(name="main_key", description=(
        "Send a discrete key or chord (Return/Tab/Esc/arrows/F-keys or e.g. "
        "cmd+shift+r). Distinct from main_type (text). Dangerous combos require "
        "confirmation."))
    def main_key(key: str, intent: str, modifiers: list[str] | None = None,
                 count: int = 1, reversible: bool = True) -> dict:
        mods = modifiers or []
        keystr = "+".join([*mods, key])
        return organ.act(MotorAction(
            name="key", level=level_for("main_key"), target=Target(),
            declaration=Declaration(reversible=reversible, intent=intent),
            params={"key": key, "modifiers": mods, "count": count, "keystr": keystr},
        ))

    @mcp.tool(name="main_hover", description="Move the pointer to (x,y) without clicking (reveal tooltips/menus).")
    def main_hover(x: int, y: int, intent: str) -> dict:
        return organ.act(MotorAction(
            name="hover", level=level_for("main_hover"), target=_target(x, y, None, None),
            declaration=Declaration(reversible=True, intent=intent), params={"x": x, "y": y}))

    @mcp.tool(name="main_activate", description="Bring an app/window frontmost by bundle id, title, or pid.")
    def main_activate(intent: str, bundle: str = "", title: str = "", pid: int = 0) -> dict:
        params = {k: v for k, v in (("bundle", bundle), ("title", title), ("pid", pid)) if v}
        return organ.act(MotorAction(
            name="activate", level=level_for("main_activate"), target=Target(),
            declaration=Declaration(reversible=True, intent=intent), params=params))
```

- [ ] **Step 4: Run, expect PASS.** Full suite: `PYTHONPATH=src python -m pytest -q`.

- [ ] **Step 5: Commit** — `git add -A && git commit -m "feat(server): register main_key/hover/activate + double-click/modifier params; tool-set test"`

---

## Task 8: README + full suite

**Files:** Modify `README.md`, run suite

- [ ] **Step 1:** Run `PYTHONPATH=src python -m pytest -q` — all pass.
- [ ] **Step 2:** Update the README "The hands"/"senses" sections: note bounded `touche_tree` (max_depth/root/roles/summary/window), `vue_snapshot` region + 720 default, and the new tools `main_key`, `main_hover`, `main_activate`, and `main_click(button,count,modifiers)`.
- [ ] **Step 3:** Commit — `git add README.md && git commit -m "docs: bounded touché, region capture, expanded input vocabulary"`

---

## Self-review

- **Spec coverage (0a):** 0a.1 bounded tree → Tasks 1-3. 0a.2 window targeting + fallback → Task 2 (`_resolve_root`/`_window_element`). 0a.3 region snapshot + low default → Task 4. 0a.4 double-click + main_key → Tasks 5-7. F2 registration test → Task 7. ✓
- **Placeholders:** none — all code complete.
- **Type consistency:** `shape_tree`/`to_summary_lines` signatures stable across Tasks 1-3; `snapshot_tree(**kw)` matches the tool call in Task 3; `MotorAction.params` keys (`button`/`count`/`modifiers`/`key`/`keystr`) consistent across actuator (Task 6), classifier (Task 6), server (Task 7). ✓
- **Note:** 0a stays at low security delta — new gestures hit observed coordinates; the AI-label re-probe (A1) and risky vocabulary (right-click/drag/primitives) are Phase 0b. `main_click(button="right")` is *wired* here only via the generic param but right-click menus + drag land properly classified in 0b.
