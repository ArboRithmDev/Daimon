# tests/test_pacte_organ.py
from pathlib import Path

from daimon.config import ExclusionConfig
from daimon.exclusions import ExclusionFilter
from daimon.motor.audit import AppendOnlyLedger
from daimon.motor.guard import PolicyGuard
from daimon.motor.organ import MotorOrgan
from daimon.motor.types import Level
from daimon.pacte.actuator import CooperativeActuator
from daimon.pacte.client import CooperativeClient
from daimon.pacte.gate import CooperativeGate
from daimon.pacte.organ import Pacte
from daimon.pacte.session import CooperativeSession
from tests.fakes.cooperative_endpoint import FakeCooperativeEndpoint


class _Recorder:
    """Captures registered tools so a test can call them directly."""
    def __init__(self): self.tools = {}
    def tool(self, name=None, description=None):
        def deco(fn): self.tools[name] = fn; return fn
        return deco


class _NullProber:
    def observe(self, action): return action.target


def _exclusions():
    return ExclusionFilter(ExclusionConfig(window_titles=[r"1Password"]))


def _build(tmp_path, fake_ep):
    exclusions = _exclusions()
    led = AppendOnlyLedger(tmp_path / "c.jsonl")
    session = CooperativeSession(led, clock=lambda: "ts")

    def motor_factory(client):
        guard = PolicyGuard(exclusions, ceiling_provider=session.ceiling)
        return MotorOrgan(guard=guard, gate=CooperativeGate(session),
                          actuator=CooperativeActuator(client),
                          session_log=led, clock=lambda: "ts", prober=_NullProber())

    return Pacte(exclusions, session, motor_factory,
                 discover_fn=lambda _d: fake_ep, cooperative_dir=tmp_path)


def test_describe_reports_disconnected_when_no_endpoint(tmp_path):
    p = Pacte(_exclusions(), CooperativeSession(AppendOnlyLedger(tmp_path / "c.jsonl"), lambda: "ts"),
              lambda c: None, discover_fn=lambda _d: None, cooperative_dir=tmp_path)
    rec = _Recorder(); p.register(rec)
    assert rec.tools["pacte_describe"]()["connected"] is False


def test_act_drag_within_ceiling_executes(tmp_path):
    fake = FakeCooperativeEndpoint(token="secret")
    fake.handlers["describe"] = lambda p: {"act_verbs": [{"name": "drag", "level": 2}]}
    fake.handlers["act"] = lambda p: {"ok": True, "verb": p["verb"]}
    ep = fake.start()
    try:
        from daimon.pacte.discovery import Endpoint
        p = _build(tmp_path, Endpoint(port=ep.port, token="secret", pid=1, app="delta", protocol_version="1.0"))
        rec = _Recorder(); p.register(rec)
        assert rec.tools["pacte_describe"]()["connected"] is True
        out = rec.tools["pacte_act"](verb="drag", args={"target": "n1"}, intent="move", level=2)
        assert out["status"] == "done" and out["result"]["ok"] is True
    finally:
        fake.stop()


def test_act_above_session_ceiling_is_refused(tmp_path):
    fake = FakeCooperativeEndpoint(token="secret")
    fake.handlers["describe"] = lambda p: {"act_verbs": []}
    ep = fake.start()
    try:
        from daimon.pacte.discovery import Endpoint
        p = _build(tmp_path, Endpoint(port=ep.port, token="secret", pid=1, app="delta", protocol_version="1.0"))
        rec = _Recorder(); p.register(rec)
        rec.tools["pacte_describe"]()
        out = rec.tools["pacte_act"](verb="wipe", args={}, intent="x", level=int(Level.AUTONOMOUS))
        assert out["status"] == "refused"
    finally:
        fake.stop()


def test_describe_failure_does_not_open_session(tmp_path):
    """If the handshake (describe call) fails, the session must NOT be opened."""
    from daimon.pacte.discovery import Endpoint
    from daimon.pacte.protocol import ProtocolError
    # Start a fake with token "real" but build the Pacte pointing at token "wrong",
    # so the fake returns a JSON-RPC error → ProtocolError on client.call("describe").
    fake = FakeCooperativeEndpoint(token="real")
    ep_real = fake.start()
    try:
        bad_ep = Endpoint(port=ep_real.port, token="wrong", pid=1, app="delta", protocol_version="1.0")
        p = _build(tmp_path, bad_ep)
        rec = _Recorder(); p.register(rec)

        raised = False
        try:
            rec.tools["pacte_describe"]()
        except ProtocolError:
            raised = True
        assert raised, "pacte_describe should propagate the ProtocolError"

        # Session must be inactive and act must refuse.
        assert not p._session.active(), "session must not be open after a failed handshake"
        out = rec.tools["pacte_act"](verb="drag", args={}, intent="x", level=2)
        assert out["status"] == "refused"
    finally:
        fake.stop()


def test_capture_returns_image_and_scene_rect(tmp_path):
    import base64
    import json as _json

    from mcp.server.fastmcp import Image as MCPImage
    from mcp.types import TextContent
    from tests.fakes.cooperative_endpoint import _PNG_1X1

    fake = FakeCooperativeEndpoint(token="secret")
    ep = fake.start()
    try:
        from daimon.pacte.discovery import Endpoint
        p = _build(tmp_path, Endpoint(port=ep.port, token="secret", pid=1, app="delta", protocol_version="1.0"))
        rec = _Recorder(); p.register(rec)
        rec.tools["pacte_describe"]()
        out = rec.tools["pacte_capture"](target="viewport")
        # [TextContent(scene_rect), MCPImage]
        assert isinstance(out[0], TextContent) and isinstance(out[1], MCPImage)
        meta = _json.loads(out[0].text)
        assert meta["scene_rect"] == {"x": 0, "y": 0, "w": 1, "h": 1}
        assert meta["width"] == 1 and meta["height"] == 1
        assert out[1].data == base64.b64decode(_PNG_1X1)
        # the wire call carried target + default max_width
        cap_req = [r for r in fake.requests if r["method"] == "capture"][-1]
        assert cap_req["params"]["target"] == "viewport"
        assert cap_req["params"]["max_width"] == 1024
    finally:
        fake.stop()


def _build_timed(tmp_path, fake_ep, clock, sleep):
    exclusions = _exclusions()
    led = AppendOnlyLedger(tmp_path / "c.jsonl")
    session = CooperativeSession(led, clock=lambda: "ts")

    def motor_factory(client):
        guard = PolicyGuard(exclusions, ceiling_provider=session.ceiling)
        return MotorOrgan(guard=guard, gate=CooperativeGate(session),
                          actuator=CooperativeActuator(client),
                          session_log=led, clock=lambda: "ts", prober=_NullProber())

    return Pacte(exclusions, session, motor_factory,
                 discover_fn=lambda _d: fake_ep, cooperative_dir=tmp_path,
                 clock_ms=clock, sleep_ms=sleep)


def test_expect_satisfies_after_polls(tmp_path):
    fake = FakeCooperativeEndpoint(token="secret")
    fake.state["quiescent"] = False
    ep = fake.start()
    try:
        from daimon.pacte.discovery import Endpoint
        now = [0.0]; sleeps = [0]
        def sleep(ms):
            now[0] += ms; sleeps[0] += 1
            if sleeps[0] == 3:
                fake.state["quiescent"] = True
        p = _build_timed(tmp_path, Endpoint(port=ep.port, token="secret", pid=1, app="delta", protocol_version="1.0"),
                         clock=lambda: now[0], sleep=sleep)
        rec = _Recorder(); p.register(rec)
        rec.tools["pacte_describe"]()
        out = rec.tools["pacte_expect"](condition={"quiescent": True}, timeout_ms=2000, poll_ms=50)
        assert out["ok"] is True and out["satisfied"] is True
        assert out["elapsed_ms"] == 150  # 3 polls * 50ms
        assert out["final"]["quiescent"] is True
        # probed only the referenced field
        probe_reqs = [r for r in fake.requests if r["method"] == "probe"]
        assert all(r["params"].get("fields") == ["quiescent"] for r in probe_reqs)
    finally:
        fake.stop()


def test_expect_times_out(tmp_path):
    fake = FakeCooperativeEndpoint(token="secret")
    fake.state["quiescent"] = False
    ep = fake.start()
    try:
        from daimon.pacte.discovery import Endpoint
        now = [0.0]
        p = _build_timed(tmp_path, Endpoint(port=ep.port, token="secret", pid=1, app="delta", protocol_version="1.0"),
                         clock=lambda: now[0], sleep=lambda ms: now.__setitem__(0, now[0] + ms))
        rec = _Recorder(); p.register(rec)
        rec.tools["pacte_describe"]()
        out = rec.tools["pacte_expect"](condition={"quiescent": True}, timeout_ms=200, poll_ms=50)
        assert out["ok"] is False and out["satisfied"] is False
        assert out["elapsed_ms"] >= 200
    finally:
        fake.stop()


def test_expect_clamps_poll_cadence(tmp_path):
    fake = FakeCooperativeEndpoint(token="secret")
    fake.state["quiescent"] = False
    ep = fake.start()
    try:
        from daimon.pacte.discovery import Endpoint
        now = [0.0]; seen = []
        p = _build_timed(tmp_path, Endpoint(port=ep.port, token="secret", pid=1, app="delta", protocol_version="1.0"),
                         clock=lambda: now[0], sleep=lambda ms: (seen.append(ms), now.__setitem__(0, now[0] + ms)))
        rec = _Recorder(); p.register(rec)
        rec.tools["pacte_describe"]()
        rec.tools["pacte_expect"](condition={"quiescent": True}, timeout_ms=50, poll_ms=5)
        assert all(s == 20 for s in seen)  # 5ms clamped up to floor 20ms
    finally:
        fake.stop()


def test_expect_refused_without_session(tmp_path):
    p = Pacte(_exclusions(), CooperativeSession(AppendOnlyLedger(tmp_path / "c.jsonl"), lambda: "ts"),
              lambda c: None, discover_fn=lambda _d: None, cooperative_dir=tmp_path)
    rec = _Recorder(); p.register(rec)
    out = rec.tools["pacte_expect"](condition={"quiescent": True})
    assert out["status"] == "refused"


def test_capture_refused_without_session(tmp_path):
    p = Pacte(_exclusions(), CooperativeSession(AppendOnlyLedger(tmp_path / "c.jsonl"), lambda: "ts"),
              lambda c: None, discover_fn=lambda _d: None, cooperative_dir=tmp_path)
    rec = _Recorder(); p.register(rec)
    out = rec.tools["pacte_capture"](target="viewport")
    assert out["status"] == "refused"


def test_probe_redacts_excluded_titles(tmp_path):
    fake = FakeCooperativeEndpoint(token="secret")
    fake.handlers["describe"] = lambda p: {"act_verbs": []}
    fake.handlers["probe"] = lambda p: {"items": [{"id": "a", "title": "1Password vault"}, {"id": "b", "title": "canvas"}]}
    ep = fake.start()
    try:
        from daimon.pacte.discovery import Endpoint
        p = _build(tmp_path, Endpoint(port=ep.port, token="secret", pid=1, app="delta", protocol_version="1.0"))
        rec = _Recorder(); p.register(rec)
        rec.tools["pacte_describe"]()
        out = rec.tools["pacte_probe"]()
        ids = [it["id"] for it in out["items"]]
        assert ids == ["b"]   # the 1Password-titled item is pruned
    finally:
        fake.stop()
