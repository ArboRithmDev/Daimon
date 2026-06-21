"""Live smoke tests for the Windows UIA accessibility backend. Windows-only."""

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows-only backend")

# Backend dep (the [win] extra). Skip cleanly where it is not installed.
pytest.importorskip("uiautomation")


def test_is_trusted_is_true_on_windows():
    from daimon.capture import accessibility_win
    assert accessibility_win.is_trusted() is True


def test_element_at_origin_returns_a_node():
    from daimon.capture import accessibility_win
    node = accessibility_win.element_at(0, 0)
    assert isinstance(node, dict)
    assert "role" in node and "position" in node


def test_snapshot_tree_is_bounded_and_shaped():
    from daimon.capture import accessibility_win
    tree = accessibility_win.snapshot_tree(max_depth=2, max_nodes=50)
    assert isinstance(tree, dict)
    assert "role" in tree

    def count(n):
        return 1 + sum(count(c) for c in (n.get("children") or []))

    assert count(tree) <= 50


def test_snapshot_summary_mode_returns_text():
    from daimon.capture import accessibility_win
    out = accessibility_win.snapshot_tree(max_depth=2, max_nodes=50, summary=True)
    assert "summary" in out and isinstance(out["summary"], str)
