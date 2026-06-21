"""Windows native window traits for the face — scaffold. Implemented on a real
Windows host (post windows-port merge). The seam matches the macOS adapter so the
host stays branch-free.

TODO(windows):
- apply_vibrancy: DWM acrylic/Mica via DwmSetWindowAttribute
  (DWMWA_SYSTEMBACKDROP_TYPE = DWMSBT_TRANSIENTWINDOW) on the HWND.
- exclude_from_capture: SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE).
- anchor_under_statusitem: position under the tray icon via Shell_NotifyIconGetRect.
The HWND is reachable from the pywebview window's native handle (edgechromium)."""

from __future__ import annotations


class WindowsFaceAdapter:
    def run_on_main(self, fn) -> None:  # pragma: no cover - Windows
        fn()

    def apply_vibrancy(self, window, *, dark: bool = True, radius: int = 20) -> None:  # pragma: no cover - Windows
        pass

    def exclude_from_capture(self, window) -> None:  # pragma: no cover - Windows
        pass

    def set_click_through(self, window) -> None:  # pragma: no cover - Windows
        pass

    def fit_to_screen(self, window) -> None:  # pragma: no cover - Windows
        pass

    def watch_outside_click(self, window, statusitem, on_outside):  # pragma: no cover - Windows
        return None

    def anchor_under_statusitem(self, window, statusitem) -> None:  # pragma: no cover - Windows
        pass
