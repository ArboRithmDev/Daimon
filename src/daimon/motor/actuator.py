"""Physical execution of motor actions.

Prefers semantic Accessibility actions (AXPress on a re-probed element) for
`press`; uses synthetic CGEvents for click/type/drag/scroll. This is the only
module that mutates the host. Behind the `Actuator` protocol so the organ is
testable with `FakeActuator`.
"""

from __future__ import annotations

from typing import Protocol

from .types import MotorAction


class Actuator(Protocol):
    def execute(self, action: MotorAction) -> dict: ...


class FakeActuator:
    def __init__(self, fail: bool = False) -> None:
        self._fail = fail
        self.executed: list[MotorAction] = []

    def execute(self, action: MotorAction) -> dict:
        if self._fail:
            raise RuntimeError("actuator failure (simulated)")
        self.executed.append(action)
        return {"status": "executed", "action": action.name}


class MacOSActuator:
    def execute(self, action: MotorAction) -> dict:
        handler = {
            "click": self._click,
            "type": self._type,
            "drag": self._drag,
            "press": self._press,
            "navigate": self._navigate,
        }.get(action.name)
        if handler is None:
            raise ValueError(f"unknown action: {action.name}")
        handler(action)
        return {"status": "executed", "action": action.name}

    def _click(self, action: MotorAction) -> None:
        import Quartz

        x = action.params.get("x", action.target.x)
        y = action.params.get("y", action.target.y)
        for down, up in [(Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp)]:
            ev_down = Quartz.CGEventCreateMouseEvent(None, down, (x, y), Quartz.kCGMouseButtonLeft)
            ev_up = Quartz.CGEventCreateMouseEvent(None, up, (x, y), Quartz.kCGMouseButtonLeft)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev_down)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev_up)

    def _type(self, action: MotorAction) -> None:
        import Quartz

        text = action.params["text"]
        for ch in text:
            ev = Quartz.CGEventCreateKeyboardEvent(None, 0, True)
            Quartz.CGEventKeyboardSetUnicodeString(ev, len(ch), ch)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
            ev_up = Quartz.CGEventCreateKeyboardEvent(None, 0, False)
            Quartz.CGEventKeyboardSetUnicodeString(ev_up, len(ch), ch)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev_up)

    def _drag(self, action: MotorAction) -> None:
        import Quartz

        x1, y1 = action.params["from"]
        x2, y2 = action.params["to"]
        down = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseDown, (x1, y1), Quartz.kCGMouseButtonLeft)
        drag = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseDragged, (x2, y2), Quartz.kCGMouseButtonLeft)
        up = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseUp, (x2, y2), Quartz.kCGMouseButtonLeft)
        for ev in (down, drag, up):
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)

    def _press(self, action: MotorAction) -> None:
        from ApplicationServices import (
            AXUIElementCopyElementAtPosition,
            AXUIElementCreateSystemWide,
            AXUIElementPerformAction,
            kAXPressAction,
        )

        x = action.params.get("x", action.target.x)
        y = action.params.get("y", action.target.y)
        system = AXUIElementCreateSystemWide()
        err, element = AXUIElementCopyElementAtPosition(system, float(x), float(y), None)
        if err != 0 or element is None:
            raise RuntimeError(f"no element to press at ({x},{y})")
        AXUIElementPerformAction(element, kAXPressAction)

    def _navigate(self, action: MotorAction) -> None:
        import Quartz

        dy = int(action.params.get("scroll_y", 0))
        if dy:
            ev = Quartz.CGEventCreateScrollWheelEvent(None, Quartz.kCGScrollEventUnitPixel, 1, dy)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
