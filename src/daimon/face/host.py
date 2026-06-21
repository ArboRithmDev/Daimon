"""FaceHost — pywebview window lifecycle for the three face surfaces.

OS-agnostic: the actual `webview` module is lazy-imported (so unit tests inject a
fake and the package imports without pywebview installed). Native window traits
(vibrancy, anchor, capture-exclusion) are delegated to a platform adapter and are
validated on a real machine, not headless.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _dist_dir() -> Path:
    """Locate the built web bundle, in source AND in a PyInstaller-frozen app.

    Frozen: data files added by daimon.spec land under sys._MEIPASS at
    daimon/face/web/dist. Source: it sits next to this module.
    """
    base = getattr(sys, "_MEIPASS", None)
    if base is not None:
        return Path(base) / "daimon" / "face" / "web" / "dist"
    return Path(__file__).resolve().parent / "web" / "dist"


def _surface_url(surface: str) -> str:
    """Local filesystem path of a built surface's index.html. Loaded through
    pywebview's http server (start(http_server=True)) so the origin is
    http://127.0.0.1 — where the strict CSP `default-src 'self'` permits the
    bundle, unlike a null `file://` origin which blocks it."""
    return str(_dist_dir() / surface / "index.html")


class FaceHost:
    """Owns the panel / overlay / onboarding webview windows and pushes state.

    `bridge` is the FaceBridge exposed to JS as `js_api`. `webview_module`
    defaults to the real `webview` (pywebview), lazily imported on first use;
    tests pass a fake recording module.
    """

    def __init__(self, bridge, webview_module=None, adapter=None) -> None:
        self._bridge = bridge
        self._wv = webview_module
        self._windows: dict[str, object] = {}
        if adapter is None:
            from .platform import get_adapter
            adapter = get_adapter()
        self._adapter = adapter

    def _on_shown(self, win, fn) -> None:
        """Run a native tweak once the window exists (its NSWindow handle is set
        on the 'shown' event). The event fires on a background thread, but NSWindow
        management must run on the main thread — marshal via the adapter. Guarded
        for fake webview windows without events."""
        runner = getattr(self._adapter, "run_on_main", lambda f: f())
        events = getattr(win, "events", None)
        if events is not None and hasattr(events, "shown"):
            events.shown += (lambda: runner(fn))
        else:
            fn()  # no event system (tests) — call directly

    def _webview(self):
        if self._wv is None:
            import webview  # lazy: only needed when actually opening a window
            self._wv = webview
        return self._wv

    # The panel card is 322px wide; the window is a touch wider/taller and
    # transparent so the rounded card floats (rest = desktop, then native
    # vibrancy). Auto-fit-to-content is a later refinement.
    PANEL_W = 322
    PANEL_H = 780

    def open_panel(self):
        """Menu-bar dropdown: frameless, transparent, fixed-size; (native)
        vibrancy + anchor + dismiss-on-blur come from the platform adapter."""
        win = self._webview().create_window(
            "Daimon", _surface_url("panel"), js_api=self._bridge, frameless=True,
            width=self.PANEL_W, height=self.PANEL_H, transparent=True, resizable=False,
        )
        self._windows["panel"] = win
        # Let the panel fit the window to its measured content height.
        setter = getattr(self._bridge, "set_resizer", None)
        if setter is not None:
            setter(lambda w, h: win.resize(w, h))
        # Frosted vibrancy backdrop once the native window exists.
        self._on_shown(win, lambda: self._adapter.apply_vibrancy(win, dark=True))
        return win

    def open_overlay(self):
        """On-screen companion face: a screen-wide transparent, click-through,
        capture-excluded, always-on-top canvas (the daemon's presence; room for
        future AI drawing)."""
        win = self._webview().create_window(
            "Daimon Overlay", _surface_url("overlay"), js_api=self._bridge,
            frameless=True, transparent=True, on_top=True,
        )
        self._windows["overlay"] = win

        def _native():
            self._adapter.exclude_from_capture(win)  # never in a screenshot (doctrine)
            self._adapter.set_click_through(win)
            self._adapter.fit_to_screen(win)

        self._on_shown(win, _native)
        return win

    ONBOARDING_W = 460
    ONBOARDING_H = 640

    def open_onboarding(self):
        """First-run window — frameless, frosted, fixed-size; closes itself via the
        bridge ('Finish')."""
        win = self._webview().create_window(
            "Welcome to Daimon", _surface_url("onboarding"), js_api=self._bridge,
            frameless=True, transparent=True, resizable=False,
            width=self.ONBOARDING_W, height=self.ONBOARDING_H,
        )
        self._windows["onboarding"] = win
        closer = getattr(self._bridge, "set_closer", None)
        if closer is not None:
            closer(lambda: win.destroy())
        self._on_shown(win, lambda: self._adapter.apply_vibrancy(win, dark=True, radius=24))
        return win

    def push_state(self) -> None:
        """Push a fresh serialized state to every open window (Python -> JS)."""
        payload = json.dumps(self._bridge.get_state())
        js = f"window.dispatchEvent(new CustomEvent('daimon:state',{{detail:{payload}}}))"
        for win in self._windows.values():
            win.evaluate_js(js)
