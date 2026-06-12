"""macOS Accessibility backend for the Touché sense.

Reads the AXUIElement tree via the Accessibility API (pyobjc /
ApplicationServices). Requires the host process to hold Accessibility
permission (System Settings → Privacy & Security → Accessibility).

Read-only by contract: this module only *copies* attribute values. It never
performs an AX action. Nodes are plain dicts so they serialize straight to MCP.

Two entry points mirror the two granularities of Touché:
  - snapshot_tree(): full tree of the frontmost app's focused window (passif).
  - element_at(x, y): the single element under a screen point (actif).
"""

from __future__ import annotations

from typing import Any

from .treeshape import shape_tree, to_summary_lines

_DEFAULT_MAX_DEPTH = 4


def is_trusted() -> bool:
    """Whether this process is allowed to use the Accessibility API."""
    from ApplicationServices import AXIsProcessTrusted

    return bool(AXIsProcessTrusted())


def _copy_attr(element, attr: str):
    from ApplicationServices import AXUIElementCopyAttributeValue

    err, value = AXUIElementCopyAttributeValue(element, attr, None)
    if err != 0:
        return None
    return value


def _point_size(element) -> tuple[dict | None, dict | None]:
    """Best-effort (position, size) as plain dicts; None if unavailable."""
    from ApplicationServices import (
        AXValueGetValue,
        kAXPositionAttribute,
        kAXSizeAttribute,
        kAXValueCGPointType,
        kAXValueCGSizeType,
    )

    pos = None
    size = None
    raw_pos = _copy_attr(element, kAXPositionAttribute)
    if raw_pos is not None:
        ok, pt = AXValueGetValue(raw_pos, kAXValueCGPointType, None)
        if ok:
            pos = {"x": round(pt.x), "y": round(pt.y)}
    raw_size = _copy_attr(element, kAXSizeAttribute)
    if raw_size is not None:
        ok, sz = AXValueGetValue(raw_size, kAXValueCGSizeType, None)
        if ok:
            size = {"width": round(sz.width), "height": round(sz.height)}
    return pos, size


def _stringify(value) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def node_from_element(element, *, with_geometry: bool = True) -> dict:
    """Flatten a single AXUIElement to a dict (no children)."""
    from ApplicationServices import (
        kAXDescriptionAttribute,
        kAXRoleAttribute,
        kAXSubroleAttribute,
        kAXTitleAttribute,
        kAXValueAttribute,
    )

    node: dict[str, Any] = {
        "role": _stringify(_copy_attr(element, kAXRoleAttribute)),
        "subrole": _stringify(_copy_attr(element, kAXSubroleAttribute)),
        "title": _stringify(_copy_attr(element, kAXTitleAttribute)),
        "value": _stringify(_copy_attr(element, kAXValueAttribute)),
        "description": _stringify(_copy_attr(element, kAXDescriptionAttribute)),
    }
    if with_geometry:
        pos, size = _point_size(element)
        node["position"] = pos
        node["size"] = size
    return node


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
    pid = _frontmost_pid()
    if pid is None:
        raise RuntimeError("No frontmost application.")
    app_el = AXUIElementCreateApplication(pid)
    win = _copy_attr(app_el, kAXFocusedWindowAttribute)
    return win if win is not None else app_el


def _frontmost_pid() -> int | None:
    from AppKit import NSWorkspace

    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return int(app.processIdentifier()) if app else None


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


def element_at(x: int, y: int) -> dict:
    """Touché actif: the element under a screen point."""
    from ApplicationServices import (
        AXUIElementCopyElementAtPosition,
        AXUIElementCreateSystemWide,
    )

    system = AXUIElementCreateSystemWide()
    err, element = AXUIElementCopyElementAtPosition(system, float(x), float(y), None)
    if err != 0 or element is None:
        raise RuntimeError(f"No accessibility element at ({x}, {y}) [err={err}].")
    return node_from_element(element)


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
