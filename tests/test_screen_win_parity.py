"""Windows backend parity — the pure rect→Display shaping.

Origin must be surfaced from the monitor rect (left/top), exactly as the macOS
backend surfaces it from CGDisplayBounds, so coord-space is platform-identical.
The pure shaping (display_from_monitor) is exercised on any platform; the live
Win32 runtime (list_displays/dpi_for_monitor/capture_display) is real and only
runs on Windows — off Windows it fails fast on the missing pywin32 stack.
"""

import sys

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


def test_runtime_calls_require_win32_stack():
    # The Win32 runtime calls are REAL now (no longer scaffolded). On Windows
    # they actually enumerate/capture; off Windows they fail fast on the missing
    # pywin32 stack rather than silently returning bogus geometry.
    if sys.platform == "win32":
        pytest.skip("on Windows the runtime calls run for real")
    with pytest.raises((ModuleNotFoundError, ImportError)):
        screen_win.list_displays()
    with pytest.raises((ModuleNotFoundError, ImportError)):
        screen_win.dpi_for_monitor(1)
    with pytest.raises((ModuleNotFoundError, ImportError)):
        screen_win.capture_display()


def test_win_backend_shares_pure_shapes_with_mac():
    # Single source of truth: the win twin re-exports the mac dataclasses.
    assert screen_win.Display is Display
    assert screen_win.Frame is Frame


def test_display_from_monitor_carries_stable_id():
    # The CCD device path rides through into the Display so calibration can
    # identify the physical panel natively.
    d = screen_win.display_from_monitor(
        index=0, monitor_handle=1, rect=(0, 0, 1920, 1080), dpi=96, is_main=True,
        stable_id=r"\\?\DISPLAY#DELA0AB#5&abc#{GUID}",
    )
    assert d.stable_id == r"\\?\DISPLAY#DELA0AB#5&abc#{GUID}"


def test_display_from_monitor_stable_id_defaults_empty():
    # No CCD identity available -> empty, calibration falls back to geometry.
    d = screen_win.display_from_monitor(
        index=0, monitor_handle=1, rect=(0, 0, 1920, 1080), dpi=96, is_main=True,
    )
    assert d.stable_id == ""


def test_native_monitor_ids_is_best_effort():
    # Pure ctypes against user32: returns a dict on Windows (gdi name -> device
    # path), and degrades to {} anywhere the CCD API is unavailable — never raises.
    ids = screen_win.native_monitor_ids()
    assert isinstance(ids, dict)
    if sys.platform == "win32":
        for gdi, path in ids.items():
            assert gdi.startswith(r"\\.\DISPLAY")
            assert path  # a non-empty stable device path


def test_live_displays_are_natively_identified_on_windows():
    # End-to-end on a real Windows host: each live display carries its CCD id
    # and the environment signature is the native (panel-set) regime.
    if sys.platform != "win32":
        pytest.skip("real CCD identity only on Windows")
    from daimon.senses.calibration import environment_signature
    displays = screen_win.list_displays()
    assert displays
    # On a normal desktop CCD is available; if a host has none, fall back is fine.
    if all(d.stable_id for d in displays):
        from dataclasses import replace
        bumped = [replace(d, width=d.width // 2 or 1, dpi=d.dpi + 24) for d in displays]
        assert environment_signature(bumped) == environment_signature(displays)
