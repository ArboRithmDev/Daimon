"""Windows UI Automation backend for the Touché sense.

The Windows twin of ``accessibility.py`` (macOS AX). Reads the UIA element tree
via the ``uiautomation`` package (a thin wrapper over the IUIAutomation COM
API). Read-only by contract: it only *copies* properties, never invokes a
pattern. Nodes are plain dicts so they serialize straight to MCP, and the pure
``treeshape`` shaper is shared with the macOS backend.

Windows has no TCC-style permission gate for UIA, so ``is_trusted()`` is always
True. Password fields (UIA ``IsPassword``) are surfaced with role
``AXSecureTextField`` — the canonical secret role the exclusion filter already
blanks — and their value is never copied out of the backend (defence in depth).
"""

from __future__ import annotations

from typing import Any

from .treeshape import shape_tree, to_summary_lines

_DEFAULT_MAX_DEPTH = 4
# Role the exclusion filter treats as secret (config default secret_roles).
_SECRET_ROLE = "AXSecureTextField"


def is_trusted() -> bool:
    """UIA needs no per-app permission grant on Windows."""
    return True


def _value(control) -> Any:
    """Best-effort text value via Value or LegacyIAccessible pattern; None on miss."""
    for getter in ("GetValuePattern", "GetLegacyIAccessiblePattern"):
        fn = getattr(control, getter, None)
        if fn is None:
            continue
        try:
            v = getattr(fn(), "Value", None)
            if v:
                return v
        except Exception:
            pass
    return None


def _point_size(control) -> tuple[dict | None, dict | None]:
    try:
        r = control.BoundingRectangle
        if r is None or r.isempty():
            return None, None
        return (
            {"x": int(r.left), "y": int(r.top)},
            {"width": int(r.width()), "height": int(r.height())},
        )
    except Exception:
        return None, None


def _stringify(value) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def node_from_element(control, *, with_geometry: bool = True) -> dict:
    """Flatten a single UIA control to a dict (no children)."""
    is_secret = False
    try:
        is_secret = bool(control.IsPassword)
    except Exception:
        is_secret = False

    role = _SECRET_ROLE if is_secret else _stringify(control.ControlTypeName)
    # Never copy a password value out of the backend.
    value = None if is_secret else _stringify(_value(control))

    node: dict[str, Any] = {
        "role": role,
        "subrole": None,
        "title": _stringify(getattr(control, "Name", None)),
        "value": value,
        "description": _stringify(getattr(control, "HelpText", None)),
    }
    if with_geometry:
        pos, size = _point_size(control)
        node["position"] = pos
        node["size"] = size
    return node


def _raw_tree(root, max_nodes: int) -> dict:
    """Walk the UIA tree into plain dicts, capped by node count (depth/role
    shaping happens later in the pure treeshape module)."""
    counter = [0]

    def walk(control) -> dict:
        node = node_from_element(control)
        counter[0] += 1
        if counter[0] >= max_nodes:
            node["children_truncated"] = True
            return node
        try:
            children = control.GetChildren()
        except Exception:
            children = []
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


def _window_control(window: dict):
    """Resolve a top-level window control by {pid|title}."""
    import uiautomation as auto

    pid = window.get("pid")
    title = window.get("title")
    for top in auto.GetRootControl().GetChildren():
        try:
            if pid is not None and int(getattr(top, "ProcessId", -1)) == int(pid):
                return top
            if title and getattr(top, "Name", None) == title:
                return top
        except Exception:
            continue
    raise RuntimeError(f"No window matching {window}")


def _resolve_root(window, root_point):
    import uiautomation as auto

    if root_point is not None:
        el = auto.ControlFromPoint(int(root_point["x"]), int(root_point["y"]))
        if el is None:
            raise RuntimeError(f"No element at {root_point}")
        return el
    if window is not None:
        return _window_control(window)
    fg = auto.GetForegroundControl()
    # No active foreground window (e.g. nothing focused, or a background run):
    # fall back to the desktop root, which is always available.
    return fg if fg is not None else auto.GetRootControl()


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
    """Touché passif, bounded. ``root``={x,y} dumps a subtree; ``window``=
    {pid|title} targets a specific window instead of the foreground."""
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
    import uiautomation as auto

    el = auto.ControlFromPoint(int(x), int(y))
    if el is None:
        raise RuntimeError(f"No UIA element at ({x}, {y}).")
    return node_from_element(el)


def focused_element() -> dict:
    """The system-wide focused UI element."""
    import uiautomation as auto

    el = auto.GetFocusedControl()
    if el is None:
        raise RuntimeError("No focused element.")
    return node_from_element(el)
