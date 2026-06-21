"""Physical execution of motor actions on Windows.

The Windows twin of ``actuator.py`` (macOS CGEvent). Uses ``SendInput`` for
mouse/keyboard/scroll and the UIA ``InvokePattern`` for semantic ``press`` (the
re-probed element under the point). This is the only Windows module that mutates
the host. Behind the same ``Actuator`` protocol, so the organ stays testable
with ``FakeActuator``.

Key differences from macOS: modifiers are real keys held around the main key
(no flag mask), and Unicode text is typed via ``KEYEVENTF_UNICODE`` (the direct
parity of CGEventKeyboardSetUnicodeString).
"""

from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

from .types import MotorAction
from .watchdog import HoldWatchdog

# --- SendInput plumbing -----------------------------------------------------

_user32 = ctypes.WinDLL("user32", use_last_error=True)

_INPUT_MOUSE = 0
_INPUT_KEYBOARD = 1

_KEYEVENTF_KEYUP = 0x0002
_KEYEVENTF_UNICODE = 0x0004

_MOUSEEVENTF_MOVE = 0x0001
_MOUSEEVENTF_LEFTDOWN = 0x0002
_MOUSEEVENTF_LEFTUP = 0x0004
_MOUSEEVENTF_RIGHTDOWN = 0x0008
_MOUSEEVENTF_RIGHTUP = 0x0010
_MOUSEEVENTF_MIDDLEDOWN = 0x0020
_MOUSEEVENTF_MIDDLEUP = 0x0040
_MOUSEEVENTF_WHEEL = 0x0800

_WHEEL_DELTA = 120
_ULONG_PTR = wintypes.WPARAM


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD), ("dwExtraInfo", _ULONG_PTR)]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                ("dwExtraInfo", _ULONG_PTR)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]


def _send(*inputs: _INPUT) -> None:
    n = len(inputs)
    arr = (_INPUT * n)(*inputs)
    sent = _user32.SendInput(n, arr, ctypes.sizeof(_INPUT))
    if sent != n:
        raise ctypes.WinError(ctypes.get_last_error())


def _mouse(flags: int, data: int = 0) -> _INPUT:
    return _INPUT(type=_INPUT_MOUSE,
                  u=_INPUTUNION(mi=_MOUSEINPUT(0, 0, data & 0xFFFFFFFF, flags, 0, 0)))


def _key_vk(vk: int, up: bool = False) -> _INPUT:
    flags = _KEYEVENTF_KEYUP if up else 0
    return _INPUT(type=_INPUT_KEYBOARD, u=_INPUTUNION(ki=_KEYBDINPUT(vk, 0, flags, 0, 0)))


def _key_unicode(ch: str, up: bool = False) -> _INPUT:
    flags = _KEYEVENTF_UNICODE | (_KEYEVENTF_KEYUP if up else 0)
    return _INPUT(type=_INPUT_KEYBOARD, u=_INPUTUNION(ki=_KEYBDINPUT(0, ord(ch), flags, 0, 0)))


def _set_cursor(x: int, y: int) -> None:
    _user32.SetCursorPos(int(x), int(y))


_BUTTONS = {
    "left": (_MOUSEEVENTF_LEFTDOWN, _MOUSEEVENTF_LEFTUP),
    "right": (_MOUSEEVENTF_RIGHTDOWN, _MOUSEEVENTF_RIGHTUP),
    "middle": (_MOUSEEVENTF_MIDDLEDOWN, _MOUSEEVENTF_MIDDLEUP),
}


# --- Actuator ---------------------------------------------------------------

class WindowsActuator:
    def __init__(self) -> None:
        self._watchdog = HoldWatchdog(
            timeout=10.0, release=self._auto_release, clock=time.monotonic)

    def _handlers(self):
        return {
            "click": self._click, "type": self._type, "drag": self._drag,
            "press": self._press, "navigate": self._navigate, "key": self._key,
            "hover": self._hover, "activate": self._activate,
            "mouse_down": self._mouse_down, "mouse_up": self._mouse_up,
            "key_down": self._key_down, "key_up": self._key_up,
            "window_minimize": self._window_minimize,
            "window_hide": self._window_hide,
            "window_show": self._window_show,
        }

    def execute(self, action: MotorAction) -> dict:
        self._watchdog.tick()
        handler = self._handlers().get(action.name)
        if handler is None:
            raise ValueError(f"unknown action: {action.name}")
        handler(action)
        return {"status": "executed", "action": action.name}

    # -- helpers --
    def _xy(self, action: MotorAction):
        return (action.params.get("x", action.target.x),
                action.params.get("y", action.target.y))

    def _mods_down(self, action: MotorAction) -> list[int]:
        from .keys_win import modifier_vks
        vks = modifier_vks(action.params.get("modifiers", []))
        for vk in vks:
            _send(_key_vk(vk, up=False))
        return vks

    def _mods_up(self, vks: list[int]) -> None:
        for vk in reversed(vks):
            _send(_key_vk(vk, up=True))

    # -- handlers --
    def _click(self, action: MotorAction) -> None:
        x, y = self._xy(action)
        button = action.params.get("button", "left")
        count = int(action.params.get("count", 1))
        down, up = _BUTTONS[button]
        if x is not None and y is not None:
            _set_cursor(x, y)
        mods = self._mods_down(action)
        try:
            for _ in range(count):
                _send(_mouse(down))
                _send(_mouse(up))
        finally:
            self._mods_up(mods)

    def _type(self, action: MotorAction) -> None:
        for ch in action.params["text"]:
            _send(_key_unicode(ch, up=False))
            _send(_key_unicode(ch, up=True))

    def _key(self, action: MotorAction) -> None:
        from .keys_win import vk_for
        vk = vk_for(action.params["key"])
        count = int(action.params.get("count", 1))
        mods = self._mods_down(action)
        try:
            for _ in range(count):
                _send(_key_vk(vk, up=False))
                _send(_key_vk(vk, up=True))
        finally:
            self._mods_up(mods)

    def _drag(self, action: MotorAction) -> None:
        x1, y1 = action.params["from_x"], action.params["from_y"]
        x2, y2 = action.params["to_x"], action.params["to_y"]
        _set_cursor(x1, y1)
        _send(_mouse(_MOUSEEVENTF_LEFTDOWN))
        _set_cursor(x2, y2)
        _send(_mouse(_MOUSEEVENTF_MOVE))
        _send(_mouse(_MOUSEEVENTF_LEFTUP))

    def _press(self, action: MotorAction) -> None:
        """Semantic activation via UIA InvokePattern on the element under the point."""
        import uiautomation as auto
        x, y = self._xy(action)
        ctrl = auto.ControlFromPoint(int(x), int(y))
        if ctrl is None:
            raise RuntimeError(f"no element to press at ({x},{y})")
        for getter, call in (
            ("GetInvokePattern", "Invoke"),
            ("GetTogglePattern", "Toggle"),
            ("GetSelectionItemPattern", "Select"),
            ("GetLegacyIAccessiblePattern", "DoDefaultAction"),
        ):
            fn = getattr(ctrl, getter, None)
            if fn is None:
                continue
            try:
                pattern = fn()
                getattr(pattern, call)()
                return
            except Exception:
                continue
        raise RuntimeError(f"no invokable pattern on element at ({x},{y})")

    def _navigate(self, action: MotorAction) -> None:
        dy = int(action.params.get("scroll_y", 0))
        if dy:
            # macOS scroll is in pixels; Windows wheel is in notches (WHEEL_DELTA).
            notches = max(1, abs(dy) // _WHEEL_DELTA) if abs(dy) >= _WHEEL_DELTA else 1
            data = (_WHEEL_DELTA if dy > 0 else -_WHEEL_DELTA) * notches
            _send(_mouse(_MOUSEEVENTF_WHEEL, data=data))

    def _hover(self, action: MotorAction) -> None:
        x, y = self._xy(action)
        if x is not None and y is not None:
            _set_cursor(x, y)
            _send(_mouse(_MOUSEEVENTF_MOVE))

    def _resolve_hwnd(self, params: dict):
        """First visible top-level window matching params (title substring or pid).

        Shared by activate + the window ops, mirroring the macOS twin's
        _running_app(params) resolution.
        """
        import win32gui
        import win32process
        target = {"hwnd": None}

        def _enum(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            try:
                if params.get("title") and params["title"] in win32gui.GetWindowText(hwnd):
                    target["hwnd"] = hwnd
                elif params.get("pid"):
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    if int(pid) == int(params["pid"]):
                        target["hwnd"] = hwnd
            except Exception:
                pass

        win32gui.EnumWindows(_enum, None)
        if target["hwnd"] is None:
            raise RuntimeError(f"No window matching {params}")
        return target["hwnd"]

    def _activate(self, action: MotorAction) -> None:
        import win32gui
        win32gui.SetForegroundWindow(self._resolve_hwnd(action.params))

    def _window_minimize(self, action: MotorAction) -> None:
        # macOS twin: AXMinimized=True. SW_MINIMIZE=6.
        import win32gui
        win32gui.ShowWindow(self._resolve_hwnd(action.params), 6)

    def _window_hide(self, action: MotorAction) -> None:
        # macOS twin: NSRunningApplication.hide(). SW_HIDE=0.
        import win32gui
        win32gui.ShowWindow(self._resolve_hwnd(action.params), 0)

    def _window_show(self, action: MotorAction) -> None:
        # macOS twin: unhide + AXMinimized=False + activate. SW_RESTORE=9.
        import win32gui
        hwnd = self._resolve_hwnd(action.params)
        win32gui.ShowWindow(hwnd, 9)
        win32gui.SetForegroundWindow(hwnd)

    def _mouse_down(self, action: MotorAction) -> None:
        x, y = self._xy(action)
        if x is not None and y is not None:
            _set_cursor(x, y)
        _send(_mouse(_MOUSEEVENTF_LEFTDOWN))
        self._watchdog.hold("mouse_left")

    def _mouse_up(self, action: MotorAction) -> None:
        x, y = self._xy(action)
        if x is not None and y is not None:
            _set_cursor(x, y)
        _send(_mouse(_MOUSEEVENTF_LEFTUP))
        self._watchdog.release_hold("mouse_left")

    def _key_down(self, action: MotorAction) -> None:
        from .keys_win import vk_for
        self._mods_down(action)
        _send(_key_vk(vk_for(action.params["key"]), up=False))
        self._watchdog.hold(f"key_{action.params['key']}")

    def _key_up(self, action: MotorAction) -> None:
        from .keys_win import vk_for
        _send(_key_vk(vk_for(action.params["key"]), up=True))
        self._watchdog.release_hold(f"key_{action.params['key']}")

    def _auto_release(self, handle: str) -> None:
        """Fail-safe release called by the watchdog for past-deadline holds."""
        try:
            if handle == "mouse_left":
                _send(_mouse(_MOUSEEVENTF_LEFTUP))
            elif handle.startswith("key_"):
                from .keys_win import vk_for
                _send(_key_vk(vk_for(handle[len("key_"):]), up=True))
        except Exception:
            pass
