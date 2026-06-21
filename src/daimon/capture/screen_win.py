"""Windows screen-capture backend for the Vue sense.

Captures a monitor as a PIL image via Pillow's ImageGrab (BitBlt) — the Windows
twin of ``screen.py`` (Quartz). Returns raw pixels only; Daimon does no
vision/OCR.

Why not WGC: the ``windows-capture`` (Windows.Graphics.Capture) package pulls in
OpenCV (cv2, ~109 MB), whose first import in a frozen exe stalls for *minutes*
(antivirus scanning the DLLs cold) — and bloats the bundle. BitBlt via ImageGrab
is already in Pillow (a core dep), imports instantly, and is fully sufficient for
desktop perception. The overlay stays invisible to capture either way: that is
enforced by the overlay window's ``WDA_EXCLUDEFROMCAPTURE`` affinity, which BitBlt
honours too — not by the capture backend.

The process is made per-monitor DPI-aware so monitor rectangles, captured pixels,
UIA bounds and pointer coordinates all share one physical coordinate space.
"""

from __future__ import annotations

# Shared pure types + crop (screen.py has no module-level OS import).
from .screen import Display, Frame, crop_region
# CCD native panel identity (pure ctypes, cheap to import; no win32 cost).
from .display_identity_win import native_monitor_ids

__all__ = [
    "Display", "Frame", "crop_region",
    "display_from_monitor", "dpi_for_monitor", "native_monitor_ids",
    "frontmost_bundle_id", "list_displays",
    "capture_display", "capture_main_display",
]


def display_from_monitor(index: int, monitor_handle: int,
                         rect: tuple[int, int, int, int], dpi: int,
                         is_main: bool, stable_id: str = "") -> Display:
    """Build a Display from a Win32 monitor rect (left, top, right, bottom) + dpi.

    Pure: the rect's left/top *is* the global origin (read from GetMonitorInfo),
    width/height fall out of the rect. Surfacing the origin is what makes the
    Windows backend feed the SAME coord-space as the macOS one (which reads it
    from CGDisplayBounds) — without it, every monitor reports origin (0, 0) and
    multi-display coord reprojection silently breaks.

    `stable_id` is the CCD device path (Microsoft-native panel identity) so a
    saved calibration profile re-matches the same monitors across resolution /
    DPI / layout changes; empty when CCD is unavailable (falls back to geometry).
    """
    left, top, right, bottom = rect
    return Display(
        index=index,
        display_id=int(monitor_handle),
        width=int(right - left),
        height=int(bottom - top),
        is_main=bool(is_main),
        origin_x=int(left),
        origin_y=int(top),
        dpi=int(dpi),
        stable_id=str(stable_id or ""),
    )


def dpi_for_monitor(display_index: int = 0) -> int:
    """Effective per-monitor DPI (PER_MONITOR_DPI v2) for a monitor by index.

    Best-effort: falls back to 96 (the Windows default logical DPI) when the
    Shcore query is unavailable. Mirrors the macOS backend's per-display dpi.
    """
    import win32api
    mons = win32api.EnumDisplayMonitors()
    if not mons:
        raise RuntimeError("No active displays found.")
    if display_index < 0 or display_index >= len(mons):
        raise IndexError(
            f"display_index {display_index} out of range (0..{len(mons) - 1})")
    hmon = mons[display_index][0]
    try:
        import ctypes
        dpi_x = ctypes.c_uint()
        dpi_y = ctypes.c_uint()
        # GetDpiForMonitor(hmon, MDT_EFFECTIVE_DPI=0, &dpiX, &dpiY)
        ctypes.windll.shcore.GetDpiForMonitor(
            int(hmon), 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y))
        return int(dpi_x.value) or 96
    except Exception:
        return 96


def _set_dpi_aware() -> None:
    """Make the process per-monitor DPI-aware so win32 monitor rects, ImageGrab
    pixels, UIA bounds and SendInput coords agree (physical pixels). Best-effort;
    harmless if already set."""
    import ctypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PER_MONITOR_DPI_AWARE
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


_set_dpi_aware()


def frontmost_bundle_id() -> str | None:
    """Full executable path of the foreground window's process — the Windows
    analogue of a macOS bundle id, for the app-level exclusion gate."""
    try:
        import win32gui
        import win32process
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        if not pid:
            return None
        import win32api
        import win32con
        h = win32api.OpenProcess(
            win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        try:
            return win32process.GetModuleFileNameEx(h, 0)
        finally:
            win32api.CloseHandle(h)
    except Exception:
        return None


def list_displays() -> list[Display]:
    """Enumerate active monitors in EnumDisplayMonitors order (index 0 first).

    Each Display carries its global origin (monitor rect left/top) and effective
    DPI so coord reprojection is platform-identical with the macOS backend.
    """
    import win32api
    native = native_monitor_ids()  # {gdi device name -> stable CCD device path}
    out: list[Display] = []
    for i, mon in enumerate(win32api.EnumDisplayMonitors()):
        hmon = mon[0]
        info = win32api.GetMonitorInfo(hmon)
        rect = info["Monitor"]  # (left, top, right, bottom)
        is_main = bool(info["Flags"] & 1)  # MONITORINFOF_PRIMARY
        stable_id = native.get(info.get("Device", ""), "")
        out.append(
            display_from_monitor(i, int(hmon), rect, dpi_for_monitor(i),
                                 is_main, stable_id=stable_id))
    return out


def _monitor_bbox(display_index: int):
    """(left, top, right, bottom) of a monitor in the virtual-screen space."""
    import win32api
    mons = win32api.EnumDisplayMonitors()
    if not mons:
        raise RuntimeError("No active displays found.")
    if display_index < 0 or display_index >= len(mons):
        raise IndexError(
            f"display_index {display_index} out of range (0..{len(mons) - 1})")
    return win32api.GetMonitorInfo(mons[display_index][0])["Monitor"]


def capture_display(display_index: int = 0, max_width: int | None = 720,
                    region: dict | None = None) -> Frame:
    """Capture one monitor by index (0 = first active), optionally downscaled.

    ``region`` is an optional {x, y, width, height} crop applied before
    downscaling. Mirrors ``screen.capture_display``.
    """
    from PIL import ImageGrab

    left, top, right, bottom = _monitor_bbox(display_index)
    try:
        img = ImageGrab.grab(bbox=(left, top, right, bottom), all_screens=True).convert("RGB")
    except OSError as e:
        # BitBlt fails when there is nothing to capture: locked screen, a monitor
        # asleep, or a disconnected/non-interactive session. Surface it clearly.
        raise RuntimeError(
            "screen capture failed — the display is locked, asleep, or inaccessible") from e
    img = crop_region(img, region)
    if max_width and img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, int(img.height * ratio)))

    fb = frontmost_bundle_id()
    return Frame(
        image=img,
        width=img.width,
        height=img.height,
        display_index=display_index,
        frontmost_bundle_id=fb,
    )


def capture_main_display(max_width: int | None = 1600) -> Frame:
    main = next((d for d in list_displays() if d.is_main), None)
    return capture_display(main.index if main else 0, max_width=max_width)
