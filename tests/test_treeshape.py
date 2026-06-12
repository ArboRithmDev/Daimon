from daimon.capture.treeshape import shape_tree, to_summary_lines


def _tree():
    return {
        "role": "AXWindow", "title": "Win", "value": None,
        "position": {"x": 0, "y": 0}, "size": {"width": 100, "height": 50},
        "children": [
            {"role": "AXGroup", "title": None, "value": None, "children": [
                {"role": "AXButton", "title": "OK", "value": None},
            ]},
            {"role": "AXUnknown", "title": None, "value": None, "description": None},
            {"role": "AXTextField", "title": None, "value": "x" * 500},
        ],
    }


def test_max_depth_caps_tree():
    out = shape_tree(_tree(), max_depth=1)
    grp = out["children"][0]
    assert "children" not in grp or grp.get("children_truncated")


def test_prune_empty_drops_decorative_nodes():
    out = shape_tree(_tree(), prune_empty=True)
    roles = [c["role"] for c in out["children"]]
    assert "AXUnknown" not in roles
    assert "AXButton" in [d["role"] for d in out["children"][0]["children"]]


def test_roles_filter_keeps_only_requested_plus_ancestors():
    out = shape_tree(_tree(), roles=["AXButton"])
    grp = next(c for c in out["children"] if c["role"] == "AXGroup")
    assert grp["children"][0]["role"] == "AXButton"
    assert all(c["role"] != "AXTextField" for c in out["children"])


def test_value_is_truncated():
    out = shape_tree(_tree(), max_value_chars=10)
    tf = next(c for c in out["children"] if c["role"] == "AXTextField")
    assert len(tf["value"]) <= 11


def test_summary_one_line_per_node():
    lines = to_summary_lines(_tree())
    assert any(line.strip().startswith("AXWindow") and "Win" in line for line in lines)
    assert any("AXButton" in line and "OK" in line for line in lines)
    assert lines[0].startswith("AXWindow") or not lines[0].startswith(" ")
