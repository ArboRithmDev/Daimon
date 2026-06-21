"""Live smoke tests for the Windows ImageGrab capture backend. Windows-only."""

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows-only backend")

# Backend deps. Skip cleanly where they are not installed.
pytest.importorskip("win32api")
pytest.importorskip("PIL")


def _grabbable() -> bool:
    """True if the desktop can be captured right now. BitBlt fails on a locked
    screen or a sleeping monitor (you cannot capture a screen you cannot see) —
    skip the live capture test in that state rather than report a false failure."""
    from PIL import ImageGrab
    try:
        ImageGrab.grab(all_screens=True)
        return True
    except OSError:
        return False


def test_list_displays_returns_at_least_one():
    from daimon.capture import screen_win
    displays = screen_win.list_displays()
    assert len(displays) >= 1
    assert any(d.is_main for d in displays)
    d = displays[0]
    assert d.width > 0 and d.height > 0


def test_capture_main_display_returns_rgb_frame():
    if not _grabbable():
        pytest.skip("desktop not capturable (screen locked / monitor asleep)")
    from daimon.capture import screen_win
    frame = screen_win.capture_main_display(max_width=320)
    assert frame.width <= 320
    assert frame.image.mode == "RGB"
    assert frame.image.size == (frame.width, frame.height)


def test_frontmost_bundle_id_is_a_path_or_none():
    from daimon.capture import screen_win
    fb = screen_win.frontmost_bundle_id()
    assert fb is None or isinstance(fb, str)
