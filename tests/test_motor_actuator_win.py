"""WindowsActuator dispatch parity. The module loads user32 at import time, so
these are Windows-only (skipped on macOS) — imports live inside the tests so
collection never touches the Win32 runtime off Windows.
"""

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows actuator")


def test_windows_actuator_dispatches_window_ops():
    from daimon.motor.actuator_win import WindowsActuator
    handlers = WindowsActuator()._handlers()
    for verb in ("window_minimize", "window_hide", "window_show"):
        assert verb in handlers


def test_windows_actuator_keeps_core_verbs():
    from daimon.motor.actuator_win import WindowsActuator
    handlers = WindowsActuator()._handlers()
    for verb in ("click", "type", "drag", "press", "navigate", "key",
                 "hover", "activate", "mouse_down", "mouse_up",
                 "key_down", "key_up"):
        assert verb in handlers
