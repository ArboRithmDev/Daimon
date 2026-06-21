"""AppKit host gestures shared by the face launchers (standalone __main__ and the
integrated tray). pywebview invokes bridge methods on a worker thread, but NSAlert
/ NSWindow must run on the main thread — these marshal accordingly."""

from __future__ import annotations

import threading


def run_on_main(fn):
    """Run fn on the AppKit main thread and return its result (blocking)."""
    from PyObjCTools import AppHelper
    box: dict = {}
    done = threading.Event()

    def wrapper():
        try:
            box["v"] = fn()
        except Exception:
            box["v"] = None
        finally:
            done.set()

    AppHelper.callAfter(wrapper)
    done.wait()
    return box.get("v")


def confirm_l4() -> bool:
    """Show the L4 consent disclaimer (main thread) and return True on Engage."""
    def dialog():
        from AppKit import NSAlert, NSAlertFirstButtonReturn
        a = NSAlert.alloc().init()
        a.setMessageText_("Engage L4 autonomy?")
        a.setInformativeText_(
            "Removes ALL per-action validation. Every action the AI requests will "
            "execute immediately, recorded in the immutable consent ledger. "
            "Disengage anytime from this menu."
        )
        a.addButtonWithTitle_("Engage")
        a.addButtonWithTitle_("Cancel")
        return a.runModal() == NSAlertFirstButtonReturn

    return bool(run_on_main(dialog))


_onboarders: list = []


def open_onboarding() -> None:
    """Open the AppKit onboarding window (main thread; kept alive)."""
    def show():
        from ..setup.gui.window import OnboardingController
        from ..setup.permissions import MacOSBackend
        controller = OnboardingController(MacOSBackend())
        controller.show()
        _onboarders.append(controller)

    run_on_main(show)
