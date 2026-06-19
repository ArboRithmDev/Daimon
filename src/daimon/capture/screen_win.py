"""Windows screen capture backend for the Vue sense — parity twin of screen.py.

The pure data shapes (`Display`, `Frame`) and the coord-space contract are shared
with the macOS backend via `capture.coordspace`; only the OS calls differ. On
Windows the display origin comes from the monitor rect (left/top) returned by
`GetMonitorInfo`, and the DPI from `GetDpiForMonitor` (per-monitor DPI v2).

This file is a parity-ready SCAFFOLD: the Win32 enumeration/capture calls are
stubbed with a clear NotImplementedError so the seam exists and the contract is
pinned, but the real GDI/Win32 runtime (only available on win32) is wired in a
follow-up. Everything that can be tested without the OS — building a `Display`
from a monitor rect+dpi, and a `Frame`'s coord-space — is pure and exercised by
the test suite on any platform.
"""

from __future__ import annotations

from .screen import Display, Frame  # shared pure data shapes — single source of truth


def display_from_monitor(index: int, monitor_handle: int, rect: tuple[int, int, int, int],
                         dpi: int, is_main: bool) -> Display:
    """Build a Display from a Win32 monitor rect (left, top, right, bottom) + dpi.

    Pure: the rect's left/top *is* the global origin (already read from
    GetMonitorInfo on the real backend), width/height fall out of the rect. This
    is the exact surfacing the cadrage calls for — the origin was always read,
    just never propagated into Display.
    """
    left, top, right, bottom = rect
    return Display(
        index=index,
        display_id=int(monitor_handle),
        width=right - left,
        height=bottom - top,
        is_main=is_main,
        origin_x=left,
        origin_y=top,
        dpi=dpi,
    )


def dpi_for_monitor(monitor_handle: int) -> int:
    """Effective DPI for a monitor via GetDpiForMonitor (MDT_EFFECTIVE_DPI).

    SCAFFOLD: the real shcore!GetDpiForMonitor call needs the Win32 runtime,
    which is not exercisable here. Returns the 96 baseline as documented; the
    live call is wired on win32.
    """
    raise NotImplementedError(
        "screen_win.dpi_for_monitor: wire shcore.GetDpiForMonitor on win32 "
        "(MDT_EFFECTIVE_DPI); falls back to 96 baseline. TODO real Win runtime."
    )


def list_displays() -> list[Display]:
    """Enumerate active monitors in stable order, origin+dpi surfaced.

    SCAFFOLD: real backend uses EnumDisplayMonitors + GetMonitorInfo (origin from
    the monitor rect left/top) + GetDpiForMonitor. Pure shaping is in
    `display_from_monitor`, already covered by parity tests.
    """
    raise NotImplementedError(
        "screen_win.list_displays: wire EnumDisplayMonitors + GetMonitorInfo + "
        "GetDpiForMonitor on win32. Pure rect→Display shaping is in "
        "display_from_monitor (tested). TODO real Win runtime."
    )


def capture_display(display_index: int = 0, max_width: int | None = 720,
                    region: dict | None = None) -> Frame:
    """Capture one monitor by index, downscaled to max_width — Windows twin.

    SCAFFOLD: real backend grabs the monitor via a GDI BitBlt of its rect into a
    DIB, converts to a PIL image, crops to `region`, then downscales — keeping the
    downscale ratio in `Frame.image_scale` and the origin/dpi from the Display, so
    the coord-space contract is identical to macOS. TODO real Win runtime.
    """
    raise NotImplementedError(
        "screen_win.capture_display: wire GDI BitBlt monitor capture on win32. "
        "Must populate Frame.display_origin_*, physical_*, image_scale, region, "
        "dpi exactly like the macOS backend so coord-space is platform-identical."
    )
