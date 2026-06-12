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

# Safety caps so a pathological UI can't produce an unbounded tree.
_MAX_DEPTH = 12
_MAX_NODES = 600


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


def _walk(element, depth: int, counter: list[int]) -> dict:
    from ApplicationServices import kAXChildrenAttribute

    node = node_from_element(element)
    counter[0] += 1

    if depth >= _MAX_DEPTH or counter[0] >= _MAX_NODES:
        node["children_truncated"] = True
        return node

    children = _copy_attr(element, kAXChildrenAttribute) or []
    child_nodes = []
    for child in children:
        if counter[0] >= _MAX_NODES:
            node["children_truncated"] = True
            break
        child_nodes.append(_walk(child, depth + 1, counter))
    if child_nodes:
        node["children"] = child_nodes
    return node


def _frontmost_pid() -> int | None:
    from AppKit import NSWorkspace

    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return int(app.processIdentifier()) if app else None


def snapshot_tree() -> dict:
    """Touché passif: tree of the frontmost app's focused window."""
    from ApplicationServices import (
        AXUIElementCreateApplication,
        kAXFocusedWindowAttribute,
    )

    pid = _frontmost_pid()
    if pid is None:
        raise RuntimeError("No frontmost application.")

    app_el = AXUIElementCreateApplication(pid)
    window = _copy_attr(app_el, kAXFocusedWindowAttribute)
    root = window if window is not None else app_el
    return _walk(root, depth=0, counter=[0])


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
