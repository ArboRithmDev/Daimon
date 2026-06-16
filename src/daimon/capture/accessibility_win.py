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


def _ensure_comtypes_gen_dir() -> None:
    """Point comtypes' generated-wrapper cache at a writable per-user dir BEFORE
    uiautomation triggers UIA code generation.

    On first UIA use comtypes generates ~360 KB of Python wrappers for the
    UIAutomation type library. Left to default, it writes them inside the
    package dir — which is the install folder for a frozen build: read-only under
    Program Files (so it regenerates every run, slowly), and freshly scanned by
    antivirus right after a build (the one-time multi-minute stall seen on a
    cold frozen exe). Anchored to the Daimon data dir (%APPDATA%\\Daimon\\
    comtypes_gen) it is generated once, persists across runs and versions, and
    survives a read-only install.
    """
    try:
        import comtypes.client
        from ..userdata import data_dir
        gen = data_dir() / "comtypes_gen"
        gen.mkdir(parents=True, exist_ok=True)
        comtypes.client.gen_dir = str(gen)
    except Exception:
        pass  # fall back to comtypes' own default; never block perception


_ensure_comtypes_gen_dir()

_uia_quieted = False


def _uia():
    """Import uiautomation, silencing its file logger on first use.

    uiautomation otherwise drops an ``@AutomationLog.txt`` in the process's
    current directory — which, for the MCP server, is wherever the AI client
    launched it. Route the log to the null device so nothing litters the user's
    folders.
    """
    global _uia_quieted
    import uiautomation as auto
    if not _uia_quieted:
        try:
            import os
            auto.Logger.SetLogFile(os.devnull)
        except Exception:
            pass
        _uia_quieted = True
    return auto


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


# UIA traversal can be slow on very complex apps (deep Chromium/Electron trees),
# where each COM property read costs milliseconds. Bound every walk in wall-clock
# time so a snapshot can never stall — the tree is returned truncated instead.
_WALK_BUDGET = 3.0


def _raw_tree(root, max_nodes: int, deadline: float | None = None) -> dict:
    """Walk the UIA tree into plain dicts, capped by node count AND a wall-clock
    deadline (depth/role shaping happens later in the pure treeshape module)."""
    import time
    counter = [0]

    def _stop() -> bool:
        return counter[0] >= max_nodes or (deadline is not None and time.monotonic() > deadline)

    def walk(control) -> dict:
        node = node_from_element(control)
        counter[0] += 1
        if _stop():
            node["children_truncated"] = True
            return node
        try:
            children = control.GetChildren()
        except Exception:
            children = []
        kids = []
        for child in children:
            if _stop():
                node["children_truncated"] = True
                break
            kids.append(walk(child))
        if kids:
            node["children"] = kids
        return node

    return walk(root)


def _window_control(window: dict):
    """Resolve a top-level window control by {pid|title}."""
    auto = _uia()

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
    auto = _uia()

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
    import time
    root_el = _resolve_root(window, root)
    raw = _raw_tree(root_el, max_nodes, deadline=time.monotonic() + _WALK_BUDGET)
    shaped = shape_tree(
        raw, max_depth=max_depth, roles=roles,
        prune_empty=prune_empty, max_value_chars=max_value_chars,
    )
    if summary:
        return {"summary": "\n".join(to_summary_lines(shaped))}
    return shaped


def element_at(x: int, y: int) -> dict:
    """Touché actif: the element under a screen point."""
    auto = _uia()

    el = auto.ControlFromPoint(int(x), int(y))
    if el is None:
        raise RuntimeError(f"No UIA element at ({x}, {y}).")
    return node_from_element(el)


def focused_element() -> dict:
    """The system-wide focused UI element."""
    auto = _uia()

    el = auto.GetFocusedControl()
    if el is None:
        raise RuntimeError("No focused element.")
    return node_from_element(el)
