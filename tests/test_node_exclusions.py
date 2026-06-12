"""redact_nodes prunes excluded a11y subtrees — pure logic, no macOS deps."""

from daimon.config import ExclusionConfig
from daimon.exclusions import ExclusionFilter


def _filter(**kw):
    return ExclusionFilter(ExclusionConfig(**kw))


def _tree():
    return {
        "role": "AXWindow",
        "title": "Editor",
        "children": [
            {"role": "AXGroup", "title": "Toolbar", "children": []},
            {"role": "AXTextField", "title": "Password field", "children": []},
            {
                "role": "AXGroup",
                "title": "Secrets panel",
                "children": [{"role": "AXStaticText", "title": "leak me"}],
            },
        ],
    }


def test_excluded_titles_pruned_with_subtree():
    f = _filter(window_titles=(r"(?i)password", r"(?i)secret"))
    out = f.redact_nodes([_tree()])[0]
    titles = [c["title"] for c in out["children"]]
    assert titles == ["Toolbar"]  # password + secrets subtree gone


def test_no_patterns_keeps_everything():
    f = _filter()
    out = f.redact_nodes([_tree()])[0]
    assert len(out["children"]) == 3


def test_does_not_mutate_input():
    tree = _tree()
    _filter(window_titles=(r"(?i)password",)).redact_nodes([tree])
    assert len(tree["children"]) == 3  # original untouched
