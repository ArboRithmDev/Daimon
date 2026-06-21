"""Windows native window traits for the face, via Win32 (ctypes). pywebview's
EdgeChromium backend exposes the hosting WinForms Form as ``window.native``; its
``.Handle`` is the HWND every call below operates on.

Mirrors the macOS adapter seam so ``face.host`` stays branch-free. Each body is
best-effort: it no-ops when the HWND isn't available yet or a DWM attribute is
unsupported on the running build, so an older Windows never hard-fails the face.
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes

# --- DWM window attributes (dwmapi) ---
_DWMWA_USE_IMMERSIVE_DARK_MODE = 20
_DWMWA_WINDOW_CORNER_PREFERENCE = 33
_DWMWA_SYSTEMBACKDROP_TYPE = 38
_DWMWCP_ROUND = 2
_DWMSBT_TRANSIENTWINDOW = 3  # acrylic — the frosted, translucent backdrop

# --- window styles / display affinity (user32) ---
_GWL_EXSTYLE = -20
_WS_EX_LAYERED = 0x00080000
_WS_EX_TRANSPARENT = 0x00000020
_WDA_EXCLUDEFROMCAPTURE = 0x00000011

# --- virtual screen metrics + SetWindowPos ---
_SM_XVIRTUALSCREEN = 76
_SM_YVIRTUALSCREEN = 77
_SM_CXVIRTUALSCREEN = 78
_SM_CYVIRTUALSCREEN = 79
_SPI_GETWORKAREA = 0x0030
_HWND_TOPMOST = -1
_SWP_NOACTIVATE = 0x0010
_SWP_NOSIZE = 0x0001


def _hwnd(window):
    """The HWND behind a pywebview EdgeChromium window, or None if not ready."""
    native = getattr(window, "native", None)
    if native is None:
        return None
    try:
        h = int(native.Handle)
        return h or None
    except Exception:
        return None


def _dwm_set_int(hwnd: int, attr: int, value: int) -> bool:
    try:
        val = ctypes.c_int(value)
        res = ctypes.windll.dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd), ctypes.c_uint(attr),
            ctypes.byref(val), ctypes.sizeof(val))
        return res == 0
    except Exception:
        return False


def _long_funcs():
    """GetWindowLong/SetWindowLong (the LONG_PTR variants on 64-bit), typed so the
    ex-style bits aren't truncated on a 64-bit HWND/style round-trip."""
    user32 = ctypes.windll.user32
    get = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
    set_ = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
    get.restype = ctypes.c_ssize_t
    get.argtypes = [wintypes.HWND, ctypes.c_int]
    set_.restype = ctypes.c_ssize_t
    set_.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    return get, set_


class WindowsFaceAdapter:
    def run_on_main(self, fn) -> None:
        # pywebview raises the `shown` event from the WinForms UI thread, so the
        # native tweaks already run on the right thread — call straight through.
        fn()

    def apply_vibrancy(self, window, *, dark: bool = True, radius: int = 20) -> None:
        """Give the panel a frosted, rounded, dark Windows surface: immersive dark
        mode + an acrylic system backdrop + rounded corners (DWM). Best-effort —
        the acrylic shows through wherever the web content is transparent."""
        hwnd = _hwnd(window)
        if not hwnd:
            return
        _dwm_set_int(hwnd, _DWMWA_USE_IMMERSIVE_DARK_MODE, 1 if dark else 0)
        _dwm_set_int(hwnd, _DWMWA_SYSTEMBACKDROP_TYPE, _DWMSBT_TRANSIENTWINDOW)
        _dwm_set_int(hwnd, _DWMWA_WINDOW_CORNER_PREFERENCE, _DWMWCP_ROUND)

    def exclude_from_capture(self, window) -> None:
        """Exclude the window from screen capture — the overlay face must never
        appear in a screenshot or recording (anti self-filming doctrine)."""
        hwnd = _hwnd(window)
        if not hwnd:
            return
        try:
            ctypes.windll.user32.SetWindowDisplayAffinity(
                wintypes.HWND(hwnd), wintypes.DWORD(_WDA_EXCLUDEFROMCAPTURE))
        except Exception:
            pass

    def set_click_through(self, window) -> None:
        """Let all mouse events pass through to the apps below (the overlay is
        presentational): add WS_EX_LAYERED | WS_EX_TRANSPARENT to the ex-style."""
        hwnd = _hwnd(window)
        if not hwnd:
            return
        try:
            get, set_ = _long_funcs()
            ex = get(wintypes.HWND(hwnd), _GWL_EXSTYLE)
            set_(wintypes.HWND(hwnd), _GWL_EXSTYLE,
                 ex | _WS_EX_LAYERED | _WS_EX_TRANSPARENT)
        except Exception:
            pass

    def fit_to_screen(self, window) -> None:
        """Size the window to the whole virtual desktop (all monitors) and float it
        on top — the overlay is a screen-wide transparent canvas."""
        hwnd = _hwnd(window)
        if not hwnd:
            return
        try:
            gsm = ctypes.windll.user32.GetSystemMetrics
            x = gsm(_SM_XVIRTUALSCREEN)
            y = gsm(_SM_YVIRTUALSCREEN)
            w = gsm(_SM_CXVIRTUALSCREEN)
            h = gsm(_SM_CYVIRTUALSCREEN)
            ctypes.windll.user32.SetWindowPos(
                wintypes.HWND(hwnd), wintypes.HWND(_HWND_TOPMOST),
                x, y, w, h, _SWP_NOACTIVATE)
        except Exception:
            pass

    def watch_outside_click(self, window, statusitem, on_outside):
        # Dismiss-on-blur via a global mouse hook is deferred; the panel is shown
        # on tray click and hidden on the next tray click for now.
        return None

    def anchor_under_statusitem(self, window, statusitem) -> None:
        """Place the panel at the bottom-right, just above the taskbar — where the
        Windows notification area lives. `statusitem` geometry isn't read yet; the
        work-area corner is a stable, monitor-aware anchor."""
        hwnd = _hwnd(window)
        if not hwnd:
            return
        try:
            rect = wintypes.RECT()
            ctypes.windll.user32.SystemParametersInfoW(
                _SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
            wr = wintypes.RECT()
            ctypes.windll.user32.GetWindowRect(wintypes.HWND(hwnd), ctypes.byref(wr))
            win_w = wr.right - wr.left
            win_h = wr.bottom - wr.top
            margin = 8
            x = rect.right - win_w - margin
            y = rect.bottom - win_h - margin
            ctypes.windll.user32.SetWindowPos(
                wintypes.HWND(hwnd), wintypes.HWND(_HWND_TOPMOST),
                x, y, 0, 0, _SWP_NOACTIVATE | _SWP_NOSIZE)
        except Exception:
            pass
