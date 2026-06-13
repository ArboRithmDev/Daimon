"""Entry point for the Daimon menu-bar tray application.

Launches a native NSStatusItem resident in the macOS menu bar.
All AppKit imports are deferred so that bare import works on any platform.
"""

from __future__ import annotations


def main() -> int:
    """Start the NSStatusItem tray app and run the AppKit event loop."""
    from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
    from PyObjCTools import AppHelper

    from .statusitem import StatusItemController

    app = NSApplication.sharedApplication()
    # Accessory policy = no Dock icon, no menu bar takeover.
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    controller = StatusItemController()
    controller.install()

    AppHelper.runEventLoop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
