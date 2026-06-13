"""Premium onboarding window: permission rows with live status + Grant buttons.

``OnboardingController`` is a pure-Python class that holds application state.
It does NOT subclass NSObject directly (that would require an AppKit import at
class-definition time, which would break bare import on non-macOS).

Button-target ObjC glue is encapsulated in ``_make_target(callback)``, which
lazily imports Foundation, defines a tiny ``_ButtonTarget(NSObject)`` subclass,
and returns a ready-to-use instance.  This keeps the module import 100% clean.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Onboarding controller
# ---------------------------------------------------------------------------

class OnboardingController:
    """Drives the premium onboarding window.

    All AppKit/ObjC calls are deferred into ``show()`` and helpers so a bare
    ``import daimon.setup.gui.window`` succeeds on any platform.
    """

    def __init__(self, backend) -> None:
        self._backend = backend
        # key -> {"dot": NSTextField, "btn": NSButton, "target": _ButtonTarget}
        self._rows: dict = {}
        self._window = None
        self._clients_label = None   # set by layout.build_panel
        self._clients_target = None  # retained against GC

    # ------------------------------------------------------------------
    # Public API consumed by __main__
    # ------------------------------------------------------------------

    def show(self) -> None:
        """Build and display the onboarding window, then start the status poller."""
        from AppKit import (
            NSApplication,
            NSWindow,
            NSWindowStyleMaskTitled,
            NSWindowStyleMaskClosable,
            NSBackingStoreBuffered,
            NSMakeRect,
            NSFloatingWindowLevel,
        )
        from .layout import build_panel

        rect = NSMakeRect(0, 0, 460, 260)
        win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            rect,
            NSWindowStyleMaskTitled | NSWindowStyleMaskClosable,
            NSBackingStoreBuffered,
            False,
        )
        win.setTitle_("Daimon — Setup")
        win.center()
        win.setLevel_(NSFloatingWindowLevel)   # above other apps' normal windows

        build_panel(self, win.contentView())

        win.makeKeyAndOrderFront_(None)
        self._window = win
        # The tray runs as an accessory (no-Dock) app, so the window won't come
        # forward or take focus unless we activate the app explicitly.
        NSApplication.sharedApplication().activateIgnoringOtherApps_(True)
        self._start_poll()

    # ------------------------------------------------------------------
    # Button-target factory (called by layout.build_panel)
    # ------------------------------------------------------------------

    def _make_target(self, callback):
        """Wrap *callback* in an ObjC object usable as a button target."""
        from ...objc_bridge import make_target
        return make_target(callback)

    # ------------------------------------------------------------------
    # Grant action
    # ------------------------------------------------------------------

    def grant(self, key: str) -> None:
        """Request the permission for *key* and open the matching Settings pane."""
        from ..permissions import PANE_SCREEN, PANE_ACCESSIBILITY

        if key == "screen_recording":
            self._backend.request_screen_recording()
            self._backend.open_pane(PANE_SCREEN)
        else:
            self._backend.request_accessibility()
            self._backend.open_pane(PANE_ACCESSIBILITY)

    # ------------------------------------------------------------------
    # Client deployment
    # ------------------------------------------------------------------

    def register_clients(self) -> None:
        """Register Daimon into every detected AI client, then refresh the label."""
        from ...applog import log_exception
        try:
            from ..deploy import install_all
            install_all()
        except Exception:
            log_exception("register_clients")
        self._update_clients()

    def _update_clients(self) -> None:
        if self._clients_label is None:
            return
        try:
            from ..deploy import client_summary
            n, m = client_summary()
            text = (f"AI apps: {n}/{m} registered" if m
                    else "AI apps: none detected")
            self._clients_label.setStringValue_(text)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Live-status poller (~1 s cadence via PyObjC run-loop integration)
    # ------------------------------------------------------------------

    def _start_poll(self) -> None:
        from PyObjCTools import AppHelper
        from ..permissions import permissions_status

        def tick() -> None:
            for perm in permissions_status(self._backend):
                self._update_row(perm)
            self._update_clients()
            AppHelper.callLater(1.0, tick)

        tick()

    # ------------------------------------------------------------------
    # Row updater
    # ------------------------------------------------------------------

    @staticmethod
    def _dot(granted: bool) -> str:
        return "🟢" if granted else "⚪️"

    def _update_row(self, perm) -> None:
        row = self._rows.get(perm.key)
        if row is not None:
            row["dot"].setStringValue_(self._dot(perm.granted))
