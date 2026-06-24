"""Unit tests for the pure pacte_expect condition DSL."""

from daimon.pacte.expect import evaluate, field_roots


def test_eq_ne():
    assert evaluate({"field": "a", "op": "eq", "value": 1}, {"a": 1})
    assert not evaluate({"field": "a", "op": "eq", "value": 2}, {"a": 1})
    assert evaluate({"field": "a", "op": "ne", "value": 2}, {"a": 1})


def test_gte_lte():
    assert evaluate({"field": "n", "op": "gte", "value": 3}, {"n": 3})
    assert evaluate({"field": "n", "op": "gte", "value": 3}, {"n": 4})
    assert not evaluate({"field": "n", "op": "gte", "value": 3}, {"n": 2})
    assert evaluate({"field": "n", "op": "lte", "value": 3}, {"n": 3})
    assert not evaluate({"field": "n", "op": "lte", "value": 3}, {"n": 4})


def test_contains_and_len_eq():
    assert evaluate({"field": "ids", "op": "contains", "value": "x"}, {"ids": ["x", "y"]})
    assert not evaluate({"field": "ids", "op": "contains", "value": "z"}, {"ids": ["x", "y"]})
    assert evaluate({"field": "s", "op": "contains", "value": "ell"}, {"s": "hello"})
    assert evaluate({"field": "ids", "op": "len_eq", "value": 2}, {"ids": ["x", "y"]})
    assert not evaluate({"field": "ids", "op": "len_eq", "value": 3}, {"ids": ["x", "y"]})


def test_missing_field_is_unsatisfied():
    assert not evaluate({"field": "nope", "op": "eq", "value": 1}, {"a": 1})
    assert not evaluate({"field": "a.b.c", "op": "eq", "value": 1}, {"a": {"b": {}}})


def test_dotted_path():
    probe = {"decorators": {"nested_overlay": {"visible": True}}}
    assert evaluate({"field": "decorators.nested_overlay.visible", "op": "eq", "value": True}, probe)
    assert not evaluate({"field": "decorators.nested_overlay.visible", "op": "eq", "value": False}, probe)


def test_quiescent_shortcut():
    assert evaluate({"quiescent": True}, {"quiescent": True})
    assert not evaluate({"quiescent": True}, {"quiescent": False})
    assert field_roots({"quiescent": True}) == {"quiescent"}


def test_combinators():
    probe = {"a": 1, "b": 2}
    assert evaluate({"all": [{"field": "a", "op": "eq", "value": 1},
                             {"field": "b", "op": "eq", "value": 2}]}, probe)
    assert not evaluate({"all": [{"field": "a", "op": "eq", "value": 1},
                                 {"field": "b", "op": "eq", "value": 9}]}, probe)
    assert evaluate({"any": [{"field": "a", "op": "eq", "value": 9},
                             {"field": "b", "op": "eq", "value": 2}]}, probe)


def test_non_comparable_is_unsatisfied_not_error():
    assert not evaluate({"field": "a", "op": "gte", "value": 3}, {"a": "str"})
    assert not evaluate({"field": "a", "op": "contains", "value": "x"}, {"a": 5})


def test_field_roots_collects_top_segments():
    cond = {"all": [{"field": "tree.children", "op": "len_eq", "value": 1},
                    {"any": [{"quiescent": True},
                             {"field": "events", "op": "len_eq", "value": 0}]}]}
    assert field_roots(cond) == {"tree", "quiescent", "events"}
