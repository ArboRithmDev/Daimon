# tests/test_pacte_organ.py
from pathlib import Path
import pytest

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
