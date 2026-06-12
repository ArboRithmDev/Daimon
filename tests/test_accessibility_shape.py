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
