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
