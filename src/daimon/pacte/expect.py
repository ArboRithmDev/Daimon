"""Pure condition DSL for pacte_expect — evaluate a frozen condition against a probe.

No I/O, no time: the organ owns the poll loop and the clock; this module only decides
whether a probe snapshot satisfies a condition, and which top-level fields a condition
references (so the loop can probe just those).

Condition grammar (FROZEN):
  leaf      : {"field": str, "op": "eq|ne|gte|lte|contains|len_eq", "value": any}
  shortcut  : {"quiescent": <v>}  ==  {"field":"quiescent","op":"eq","value":<v>}
  combinator: {"all": [cond, ...]} | {"any": [cond, ...]}
`field` may be dotted into nested probe objects, e.g. "decorators.nested_overlay.visible".
A missing field makes a leaf unsatisfied (never raises).
"""

from __future__ import annotations

_MISSING = object()


def _resolve(probe: dict, dotted: str):
    """Walk a dotted path through nested dicts; return _MISSING if any segment is absent."""
    cur = probe
    for seg in dotted.split("."):
        if not isinstance(cur, dict) or seg not in cur:
            return _MISSING
        cur = cur[seg]
    return cur


def _leaf(cond: dict, probe: dict) -> bool:
    value = _resolve(probe, cond["field"])
    if value is _MISSING:
        return False
    op, target = cond["op"], cond.get("value")
    try:
        if op == "eq":
            return value == target
        if op == "ne":
            return value != target
        if op == "gte":
            return value >= target
        if op == "lte":
            return value <= target
        if op == "contains":
            return target in value
        if op == "len_eq":
            return len(value) == target
    except TypeError:
        return False  # non-comparable / non-container → unsatisfied, never raise
    raise ValueError(f"unknown op: {op!r}")


def _normalize(cond: dict) -> dict:
    """Expand the {quiescent: v} shortcut to its leaf form."""
    if "quiescent" in cond and "field" not in cond and "op" not in cond:
        return {"field": "quiescent", "op": "eq", "value": cond["quiescent"]}
    return cond


def evaluate(cond: dict, probe: dict) -> bool:
    """Whether `probe` satisfies `cond` (recursive over all/any combinators)."""
    cond = _normalize(cond)
    if "all" in cond:
        return all(evaluate(c, probe) for c in cond["all"])
    if "any" in cond:
        return any(evaluate(c, probe) for c in cond["any"])
    return _leaf(cond, probe)


def field_roots(cond: dict) -> set[str]:
    """Top-level field names a condition references (first dotted segment of each leaf)."""
    cond = _normalize(cond)
    if "all" in cond or "any" in cond:
        roots: set[str] = set()
        for c in cond.get("all", []) + cond.get("any", []):
            roots |= field_roots(c)
        return roots
    return {cond["field"].split(".", 1)[0]}
