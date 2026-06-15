"""Windows screen-capture backend for the Vue sense.

Uses Windows.Graphics.Capture (WGC) via the ``windows-capture`` package to grab
a monitor as a PIL image — the Windows twin of ``screen.py`` (Quartz). Returns
raw pixels only; Daimon does no vision/OCR. WGC is the modern capture path and
honours per-window capture-exclusion (the overlay sets WDA_EXCLUDEFROMCAPTURE),
so Daimon's own overlay never self-films.

Daimon is pull-driven, so each call performs a *one-shot* grab: a free-threaded
WGC session is started, the first frame is copied out, and the session is
stopped immediately. The pure geometry/crop helpers and the Display/Frame value
types are shared with the macOS module.
"""

from __future__ import annotations

import threading

# Shared pure types + crop (screen.py has no module-level OS import).
from .screen import Display, Frame, crop_region

__all__ = [
    "Display", "Frame", "crop_region",
    "frontmost_bundle_id", "list_displays",
    "capture_display", "capture_main_display",
]

_CAPTURE_TIMEOUT = 5.0


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


def _grab_monitor_rgb(monitor_index: int):
    """One-shot WGC grab of a monitor → (PIL RGB image). monitor_index is
    1-based per windows-capture's convention."""
    from PIL import Image
    from windows_capture import WindowsCapture

    holder: dict = {}
    done = threading.Event()

    cap = WindowsCapture(
        cursor_capture=False,
        draw_border=False,
        monitor_index=monitor_index,
    )

    @cap.event
    def on_frame_arrived(frame, capture_control):
        try:
            buf = frame.frame_buffer  # H x W x 4, BGRA
            h, w = buf.shape[0], buf.shape[1]
            holder["rgb"] = buf[:h, :w, [2, 1, 0]].copy()  # BGR(A)->RGB
        finally:
            capture_control.stop()
            done.set()

    @cap.event
    def on_closed():
        done.set()

    control = cap.start_free_threaded()
    if not done.wait(timeout=_CAPTURE_TIMEOUT):
        try:
            control.stop()
        except Exception:
            pass
        raise RuntimeError("WGC capture timed out — no frame arrived.")
    if "rgb" not in holder:
        raise RuntimeError("WGC capture produced no frame.")
    return Image.fromarray(holder["rgb"], "RGB")


def capture_display(display_index: int = 0, max_width: int | None = 720,
                    region: dict | None = None) -> Frame:
    """Capture one monitor by index (0 = first active), optionally downscaled.

    ``region`` is an optional {x, y, width, height} crop applied before
    downscaling. Mirrors ``screen.capture_display``.
    """
    displays = list_displays()
    if not displays:
        raise RuntimeError("No active displays found.")
    if display_index < 0 or display_index >= len(displays):
        raise IndexError(
            f"display_index {display_index} out of range (0..{len(displays) - 1})"
        )

    img = _grab_monitor_rgb(display_index + 1)  # windows-capture is 1-based
    img = crop_region(img, region)
    if max_width and img.width > max_width:
        ratio = max_width / img.width
        img = img.resize((max_width, int(img.height * ratio)))

    return Frame(
        image=img,
        width=img.width,
        height=img.height,
        display_index=display_index,
        frontmost_bundle_id=frontmost_bundle_id(),
    )


def capture_main_display(max_width: int | None = 1600) -> Frame:
    main = next((d for d in list_displays() if d.is_main), None)
    return capture_display(main.index if main else 0, max_width=max_width)
