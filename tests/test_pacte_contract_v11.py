"""Contract proofs for v1.1 capabilities that ride the GENERIC pacte_act / pacte_probe:
set_prop (INPUT 2), set_motion (NONDESTRUCTIVE 1), and the probe fields inspector / tree /
serialized / quiescent. No new Daimon surface — these confirm the frozen wire contract
(verb names, levels, field passthrough) and that nested fields survive redaction (ADR-1).
"""

from daimon.motor.types import Level
from daimon.pacte.discovery import Endpoint
from tests.fakes.cooperative_endpoint import FakeCooperativeEndpoint
from tests.test_pacte_organ import _Recorder, _build


def _connected(tmp_path, fake):
    ep = fake.start()
    p = _build(tmp_path, Endpoint(port=ep.port, token=fake.token, pid=1, app="delta", protocol_version="1.0"))
    rec = _Recorder(); p.register(rec)
    rec.tools["pacte_describe"]()
    return rec


def test_set_prop_routes_at_level_2_and_forwards_args(tmp_path):
    fake = FakeCooperativeEndpoint(token="secret")
    try:
        rec = _connected(tmp_path, fake)
        out = rec.tools["pacte_act"](verb="set_prop", level=2, intent="edit x",
                                     args={"node_id": "n1", "path": "metadata.canvas.x", "value": 42})
        assert out["status"] == "done" and out["result"]["ok"] is True
        assert out["result"]["state_delta"]["value"] == 42
        act = [r for r in fake.requests if r["method"] == "act"][-1]
        assert act["params"]["verb"] == "set_prop"
        assert act["params"]["args"] == {"node_id": "n1", "path": "metadata.canvas.x", "value": 42}
    finally:
        fake.stop()


def test_set_prop_above_ceiling_refused(tmp_path):
    fake = FakeCooperativeEndpoint(token="secret")
    try:
        rec = _connected(tmp_path, fake)
        out = rec.tools["pacte_act"](verb="set_prop", level=int(Level.AUTONOMOUS), intent="x", args={})
        assert out["status"] == "refused"
    finally:
        fake.stop()


def test_inspector_probe_passthrough(tmp_path):
    fake = FakeCooperativeEndpoint(token="secret")
    fake.state["inspector"] = {"bound_node_id": "n1", "mode": "widget",
                               "fields": [{"path": "content", "label": "Text", "value": "hi", "editable": True}]}
    try:
        rec = _connected(tmp_path, fake)
        out = rec.tools["pacte_probe"](fields=["inspector"])
        assert out["inspector"]["bound_node_id"] == "n1"
        assert out["inspector"]["fields"][0]["path"] == "content"
    finally:
        fake.stop()


def test_tree_probe_nested_intact(tmp_path):
    fake = FakeCooperativeEndpoint(token="secret")
    fake.state["tree"] = {"id": "root", "type": "Screen", "canvas": None, "layout_rule": None,
                          "rendered_rect": {"x": 0, "y": 0, "w": 100, "h": 100},
                          "children": [{"id": "c1", "type": "Button", "canvas": {"x": 1, "y": 2, "w": 3, "h": 4},
                                        "layout_rule": "row", "rendered_rect": {"x": 5, "y": 6, "w": 3, "h": 4},
                                        "children": []}]}
    try:
        rec = _connected(tmp_path, fake)
        out = rec.tools["pacte_probe"](fields=["tree"])
        child = out["tree"]["children"][0]
        assert child["id"] == "c1" and child["rendered_rect"] == {"x": 5, "y": 6, "w": 3, "h": 4}
    finally:
        fake.stop()


def test_serialized_probe_passthrough(tmp_path):
    fake = FakeCooperativeEndpoint(token="secret")
    fake.state["serialized"] = "screen Main {\n  button b\n}"
    try:
        rec = _connected(tmp_path, fake)
        out = rec.tools["pacte_probe"](fields=["serialized"])
        assert out["serialized"].startswith("screen Main")
    finally:
        fake.stop()


def test_set_motion_routes_at_level_1(tmp_path):
    fake = FakeCooperativeEndpoint(token="secret")
    try:
        rec = _connected(tmp_path, fake)
        out = rec.tools["pacte_act"](verb="set_motion", level=1, intent="freeze", args={"enabled": False})
        assert out["status"] == "done" and out["result"]["enabled"] is False
        act = [r for r in fake.requests if r["method"] == "act"][-1]
        assert act["params"]["verb"] == "set_motion"
    finally:
        fake.stop()


def test_quiescent_probe_passthrough(tmp_path):
    fake = FakeCooperativeEndpoint(token="secret")
    fake.state["quiescent"] = False
    try:
        rec = _connected(tmp_path, fake)
        assert rec.tools["pacte_probe"](fields=["quiescent"])["quiescent"] is False
    finally:
        fake.stop()


def test_expect_quiescent_end_to_end(tmp_path):
    """set_motion(enabled=False) drives the fake to quiescent → pacte_expect({quiescent:true}) holds."""
    fake = FakeCooperativeEndpoint(token="secret")
    fake.state["quiescent"] = False
    try:
        rec = _connected(tmp_path, fake)
        rec.tools["pacte_act"](verb="set_motion", level=1, intent="freeze", args={"enabled": False})
        out = rec.tools["pacte_expect"](condition={"quiescent": True}, timeout_ms=500, poll_ms=20)
        assert out["ok"] is True and out["satisfied"] is True and out["final"]["quiescent"] is True
    finally:
        fake.stop()
