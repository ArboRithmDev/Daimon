"""Windows backend parity — the pure rect→Display shaping, no Win32 runtime.

Origin must be surfaced from the monitor rect (left/top), exactly as the macOS
backend surfaces it from CGDisplayBounds, so coord-space is platform-identical.
The live Win32 calls are scaffolded (NotImplementedError) until the real runtime.
"""

import pytest

from daimon.capture import screen_win
from daimon.capture.coordspace import CoordSpace
from daimon.capture.screen import Display, Frame


def test_display_from_monitor_surfaces_origin_from_rect():
    # A monitor physically left of main: rect left = -1920 -> negative origin.
    d = screen_win.display_from_monitor(
        index=1, monitor_handle=42, rect=(-1920, 0, 0, 1080), dpi=96, is_main=False,
    )
    assert isinstance(d, Display)
    assert (d.origin_x, d.origin_y) == (-1920, 0)
    assert (d.width, d.height) == (1920, 1080)
    assert d.dpi == 96 and d.is_main is False


def test_display_from_monitor_main_origin_zero():
    d = screen_win.display_from_monitor(
        index=0, monitor_handle=1, rect=(0, 0, 2560, 1440), dpi=144, is_main=True,
    )
    assert (d.origin_x, d.origin_y) == (0, 0)
    assert (d.width, d.height) == (2560, 1440)
    assert d.dpi == 144 and d.is_main is True


def test_win_display_feeds_same_coordspace_as_mac():
    # The whole point: a Win Display + downscale reprojects identically.
    d = screen_win.display_from_monitor(
        index=1, monitor_handle=7, rect=(-1920, 0, 0, 1080), dpi=96, is_main=False,
    )
    cs = CoordSpace(display_origin_x=d.origin_x, display_origin_y=d.origin_y,
                    image_scale=1600 / 1920)
    # image right edge -> source 1920 -> global -1920 + 1920 = 0
    assert cs.to_global(1600, 0) == (0, 0)


def test_scaffolded_runtime_calls_raise_not_implemented():
    with pytest.raises(NotImplementedError):
        screen_win.list_displays()
    with pytest.raises(NotImplementedError):
        screen_win.dpi_for_monitor(1)
    with pytest.raises(NotImplementedError):
        screen_win.capture_display()


def test_win_backend_shares_pure_shapes_with_mac():
    # Single source of truth: the win twin re-exports the mac dataclasses.
    assert screen_win.Display is Display
    assert screen_win.Frame is Frame
