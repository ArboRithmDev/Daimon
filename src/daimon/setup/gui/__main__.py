"""GUI onboarding entry point.

Run with::

    python -m daimon.setup.gui
    # or
    python -m daimon.onboard --gui

All AppKit / PyObjC imports are deferred inside ``main()`` so a bare
``import daimon.setup.gui.__main__`` on a non-macOS system (or in a test
runner) is clean.
"""

from __future__ import annotations


def main() -> int:
    import sys
    if sys.platform == "win32":
        from .window_win import run as win_run
        return win_run()

    from AppKit import NSApplication, NSApplicationActivationPolicyRegular
    from PyObjCTools import AppHelper
    from ..permissions import MacOSBackend
    from .window import OnboardingController

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)

    controller = OnboardingController(MacOSBackend())
    controller.show()

    app.activateIgnoringOtherApps_(True)
    AppHelper.runEventLoop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
