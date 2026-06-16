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

__all__ = [
    "Display", "Frame", "crop_region",
    "frontmost_bundle_id", "list_displays",
    "capture_display", "capture_main_display",
]


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
    """Enumerate active monitors in EnumDisplayMonitors order (index 0 first)."""
    import win32api
    out: list[Display] = []
    for i, mon in enumerate(win32api.EnumDisplayMonitors()):
        hmon = mon[0]
        info = win32api.GetMonitorInfo(hmon)
        left, top, right, bottom = info["Monitor"]
        out.append(
            Display(
                index=i,
                display_id=int(hmon),
                width=int(right - left),
                height=int(bottom - top),
                is_main=bool(info["Flags"] & 1),  # MONITORINFOF_PRIMARY
            )
        )
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
