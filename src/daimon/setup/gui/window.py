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
# ObjC button-target factory  (all macOS imports deferred inside the function)
# ---------------------------------------------------------------------------

def _make_target(callback):
    """Return an Objective-C object whose ``invoke:`` selector calls *callback*.

    A new NSObject subclass is created on the first call and cached so PyObjC
    does not re-register the class on subsequent calls.
    """
    from Foundation import NSObject
    import objc

    # Cache the class on the module so we only define it once per process.
    if not hasattr(_make_target, "_cls"):
        class _ButtonTarget(NSObject):
            def init(self):
                self = objc.super(_ButtonTarget, self).init()
                if self is None:
                    return None
                self._cb = None
                return self

            @objc.python_method
            def _set_callback(self, cb):
                self._cb = cb

            def invoke_(self, sender):
                if self._cb is not None:
                    self._cb()

        _make_target._cls = _ButtonTarget

    instance = _make_target._cls.alloc().init()
    instance._set_callback(callback)
    return instance


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

    # ------------------------------------------------------------------
    # Public API consumed by __main__
    # ------------------------------------------------------------------

    def show(self) -> None:
        """Build and display the onboarding window, then start the status poller."""
        from AppKit import (
            NSWindow,
            NSWindowStyleMaskTitled,
            NSWindowStyleMaskClosable,
            NSBackingStoreBuffered,
            NSMakeRect,
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

        build_panel(self, win.contentView())

        win.makeKeyAndOrderFront_(None)
        self._window = win
        self._start_poll()

    # ------------------------------------------------------------------
    # Button-target factory (called by layout.build_panel)
    # ------------------------------------------------------------------

    def _make_target(self, callback):
        """Wrap *callback* in an ObjC object usable as a button target."""
        return _make_target(callback)

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
    # Live-status poller (~1 s cadence via PyObjC run-loop integration)
    # ------------------------------------------------------------------

    def _start_poll(self) -> None:
        from PyObjCTools import AppHelper
        from ..permissions import permissions_status

        def tick() -> None:
            for perm in permissions_status(self._backend):
                self._update_row(perm)
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
