# tests/test_motor_navigate_target.py
"""F4 — targeted navigate.

main_navigate used to scroll 'the focused view' — the last-touched element,
often the wrong pane. Giving it an explicit (x, y) point makes the actuator
move the pointer over the intended view before scrolling, so the wheel event
lands where the client meant. Pure seam: FakeActuator records the params.
"""
from daimon.config import ExclusionConfig
from daimon.exclusions import ExclusionFilter
from daimon.motor.actuator import FakeActuator
from daimon.motor.audit import AppendOnlyLedger
from daimon.motor.gate import FakeGate
from daimon.motor.guard import PolicyGuard
from daimon.motor.organ import MotorOrgan
from daimon.motor.probe import FakeProber
from daimon.motor.types import Declaration, Level, MotorAction, Target


def _organ(tmp_path, actuator):
    guard = PolicyGuard(ExclusionFilter(ExclusionConfig()),
                        ceiling_provider=lambda: Level.NONDESTRUCTIVE)
    return MotorOrgan(
        guard=guard, gate=FakeGate(answer=True), actuator=actuator,
        session_log=AppendOnlyLedger(tmp_path / "s.jsonl"), clock=lambda: "T",
        prober=FakeProber(target=Target(observed=True)),
    )


def _navigate(params):
    return MotorAction(
        name="navigate", level=Level.NONDESTRUCTIVE, target=Target(),
        declaration=Declaration(reversible=True, intent="scroll editor"),
        params=params,
    )


def test_navigate_carries_explicit_point(tmp_path):
    act = FakeActuator()
    organ = _organ(tmp_path, act)
    out = organ.act(_navigate({"scroll_y": -120, "x": 800, "y": 400}))
    assert out["status"] == "done"
    p = act.executed[0].params
    assert p["scroll_y"] == -120 and p["x"] == 800 and p["y"] == 400


def test_navigate_without_point_still_works(tmp_path):
    act = FakeActuator()
    organ = _organ(tmp_path, act)
    out = organ.act(_navigate({"scroll_y": 60}))
    assert out["status"] == "done"
    assert act.executed[0].params.get("x") is None


# --- macOS backend: pointer-move precedes the scroll when a point is given ---

class _FakeQuartz:
    kCGEventMouseMoved = "moved"
    kCGScrollEventUnitPixel = "px"
    kCGHIDEventTap = "tap"

    def __init__(self):
        self.events = []

    def CGEventCreateMouseEvent(self, src, etype, pos, btn):
        return ("mouse", etype, pos)

    def CGEventCreateScrollWheelEvent(self, src, unit, count, dy):
        return ("scroll", dy)

    def CGEventPost(self, tap, ev):
        self.events.append(ev)


def test_macos_navigate_moves_pointer_before_scroll(monkeypatch):
    import sys
    from daimon.motor.actuator import MacOSActuator

    fake = _FakeQuartz()
    monkeypatch.setitem(sys.modules, "Quartz", fake)
    MacOSActuator()._navigate(_navigate({"scroll_y": -120, "x": 800, "y": 400}))
    # first event is the pointer move to (800,400), then the scroll
    assert fake.events[0] == ("mouse", "moved", (800, 400))
    assert fake.events[1] == ("scroll", -120)


def test_macos_navigate_no_point_only_scrolls(monkeypatch):
    import sys
    from daimon.motor.actuator import MacOSActuator

    fake = _FakeQuartz()
    monkeypatch.setitem(sys.modules, "Quartz", fake)
    MacOSActuator()._navigate(_navigate({"scroll_y": 60}))
    assert fake.events == [("scroll", 60)]
