"""Physical execution of motor actions.

Prefers semantic Accessibility actions (AXPress on a re-probed element) for
`press`; uses synthetic CGEvents for click/type/drag/scroll. This is the only
module that mutates the host. Behind the `Actuator` protocol so the organ is
testable with `FakeActuator`.
"""

from __future__ import annotations

import time
from typing import Protocol

from .types import MotorAction
from .watchdog import HoldWatchdog


class Actuator(Protocol):
    """The only thing allowed to mutate the host; swappable for testing."""

    def execute(self, action: MotorAction) -> dict: ...


class FakeActuator:
    """Test double: records actions instead of touching the host."""

    def __init__(self, fail: bool = False) -> None:
        self._fail = fail
        self.executed: list[MotorAction] = []

    def execute(self, action: MotorAction) -> dict:
        if self._fail:
            raise RuntimeError("actuator failure (simulated)")
        self.executed.append(action)
        return {"status": "executed", "action": action.name}


class MacOSActuator:
    """Real backend: drives the host via Accessibility and synthetic CGEvents."""

    def __init__(self) -> None:
        self._watchdog = HoldWatchdog(
            timeout=10.0,
            release=self._auto_release,
            clock=time.monotonic,
        )

    def execute(self, action: MotorAction) -> dict:
        """Dispatch the action to its handler after ticking the hold watchdog."""
        self._watchdog.tick()
        handler = {
            "click": self._click,
            "type": self._type,
            "drag": self._drag,
            "press": self._press,
            "navigate": self._navigate,
            "key": self._key,
            "hover": self._hover,
            "activate": self._activate,
            "mouse_down": self._mouse_down,
            "mouse_up": self._mouse_up,
            "key_down": self._key_down,
            "key_up": self._key_up,
        }.get(action.name)
        if handler is None:
            raise ValueError(f"unknown action: {action.name}")
        handler(action)
        return {"status": "executed", "action": action.name}

    def _key(self, action: MotorAction) -> None:
        import Quartz
        from .keys import keycode_for, modifier_mask
        code = keycode_for(action.params["key"])
        flags = modifier_mask(action.params.get("modifiers", []))
        count = int(action.params.get("count", 1))
        for _ in range(count):
            for is_down in (True, False):
                ev = Quartz.CGEventCreateKeyboardEvent(None, code, is_down)
                if flags:
                    Quartz.CGEventSetFlags(ev, flags)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)

    def _hover(self, action: MotorAction) -> None:
        import Quartz
        x = action.params.get("x", action.target.x); y = action.params.get("y", action.target.y)
        ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventMouseMoved, (x, y), 0)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)

    def _activate(self, action: MotorAction) -> None:
        from AppKit import NSWorkspace
        p = action.params
        for app in NSWorkspace.sharedWorkspace().runningApplications():
            if (p.get("bundle") and app.bundleIdentifier() == p["bundle"]) or \
               (p.get("title") and app.localizedName() == p["title"]) or \
               (p.get("pid") and int(app.processIdentifier()) == p["pid"]):
                app.activateWithOptions_(1 << 1)  # NSApplicationActivateIgnoringOtherApps
                return
        raise RuntimeError(f"No app matching {p}")

    def _click(self, action: MotorAction) -> None:
        import Quartz
        from .keys import modifier_mask
        x = action.params.get("x", action.target.x); y = action.params.get("y", action.target.y)
        button = action.params.get("button", "left")
        count = int(action.params.get("count", 1))
        flags = modifier_mask(action.params.get("modifiers", []))
        down_t, up_t, btn = {
            "left": (Quartz.kCGEventLeftMouseDown, Quartz.kCGEventLeftMouseUp, Quartz.kCGMouseButtonLeft),
            "right": (Quartz.kCGEventRightMouseDown, Quartz.kCGEventRightMouseUp, Quartz.kCGMouseButtonRight),
            "middle": (Quartz.kCGEventOtherMouseDown, Quartz.kCGEventOtherMouseUp, Quartz.kCGMouseButtonCenter),
        }[button]
        for i in range(count):
            for et in (down_t, up_t):
                ev = Quartz.CGEventCreateMouseEvent(None, et, (x, y), btn)
                if flags:
                    Quartz.CGEventSetFlags(ev, flags)
                if count > 1:
                    Quartz.CGEventSetIntegerValueField(ev, Quartz.kCGMouseEventClickState, i + 1)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)

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
        x1, y1 = action.params["from_x"], action.params["from_y"]
        x2, y2 = action.params["to_x"], action.params["to_y"]
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

        # F4: scroll the *intended* view, not 'the focused view'. When an explicit
        # point is given, move the pointer over it first so the wheel event is
        # routed to the view under (x, y) rather than the last-touched element.
        x = action.params.get("x"); y = action.params.get("y")
        if x is not None and y is not None:
            move = Quartz.CGEventCreateMouseEvent(
                None, Quartz.kCGEventMouseMoved, (x, y), 0)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, move)
        dy = int(action.params.get("scroll_y", 0))
        if dy:
            ev = Quartz.CGEventCreateScrollWheelEvent(None, Quartz.kCGScrollEventUnitPixel, 1, dy)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)

    def _mouse_down(self, action: MotorAction) -> None:
        import Quartz
        x = action.params.get("x", action.target.x); y = action.params.get("y", action.target.y)
        ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseDown, (x, y), Quartz.kCGMouseButtonLeft)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        self._watchdog.hold("mouse_left")

    def _mouse_up(self, action: MotorAction) -> None:
        import Quartz
        x = action.params.get("x", action.target.x); y = action.params.get("y", action.target.y)
        ev = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseUp, (x, y), Quartz.kCGMouseButtonLeft)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        self._watchdog.release_hold("mouse_left")

    def _key_down(self, action: MotorAction) -> None:
        import Quartz
        from .keys import keycode_for, modifier_mask
        ev = Quartz.CGEventCreateKeyboardEvent(None, keycode_for(action.params["key"]), True)
        flags = modifier_mask(action.params.get("modifiers", []))
        if flags:
            Quartz.CGEventSetFlags(ev, flags)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        self._watchdog.hold(f"key_{action.params['key']}")

    def _key_up(self, action: MotorAction) -> None:
        import Quartz
        from .keys import keycode_for
        ev = Quartz.CGEventCreateKeyboardEvent(None, keycode_for(action.params["key"]), False)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        self._watchdog.release_hold(f"key_{action.params['key']}")

    def _auto_release(self, handle: str) -> None:
        """Fail-safe release called by the watchdog for past-deadline holds."""
        try:
            import Quartz
            if handle == "mouse_left":
                ev = Quartz.CGEventCreateMouseEvent(
                    None, Quartz.kCGEventLeftMouseUp, (0, 0), Quartz.kCGMouseButtonLeft
                )
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
            elif handle.startswith("key_"):
                from .keys import keycode_for
                key_name = handle[len("key_"):]
                code = keycode_for(key_name)
                ev = Quartz.CGEventCreateKeyboardEvent(None, code, False)
                Quartz.CGEventPost(Quartz.kCGHIDEventTap, ev)
        except Exception:
            pass
