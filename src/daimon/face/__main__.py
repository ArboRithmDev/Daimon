"""Walking-skeleton launcher for the face panel: `python -m daimon.face`.

Opens the menu-bar panel in a real pywebview window, wired to the live organ
state (gather) and the shared TrayActions. This is the Phase-3 smoke target —
it proves the chain pywebview -> dist/panel -> bridge -> real state renders and
that actions round-trip. Native window traits (vibrancy/anchor/dismiss) come
next; this just gets the panel on screen.

Requires the built bundle (run `python build/make_face.py` first) and pywebview.
"""

from __future__ import annotations

import sys
import threading

from .bridge import FaceBridge
from .host import FaceHost
from ..tray.actions import ActionRouter
from ..tray.actions_impl import TrayActions
from ..tray.state import gather


def _run_on_main(fn):
    """Run fn on the AppKit main thread and return its result. pywebview invokes
    js_api methods on a worker thread, but NSAlert / NSWindow must run on main."""
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


def _confirm_l4() -> bool:
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

    return bool(_run_on_main(dialog))


_onboarders: list = []


def _open_onboarding() -> None:
    def show():
        from ..setup.gui.window import OnboardingController
        from ..setup.permissions import MacOSBackend
        controller = OnboardingController(MacOSBackend())
        controller.show()
        _onboarders.append(controller)  # keep alive

    _run_on_main(show)


def main() -> int:
    import webview

    host: FaceHost | None = None

    def push():
        if host is not None:
            host.push_state()

    def quit_all():
        for w in list(getattr(webview, "windows", [])):
            try:
                w.destroy()
            except Exception:
                pass

    handlers = TrayActions(
        on_change=push,
        confirm_l4=_confirm_l4,
        open_onboarding=_open_onboarding,
        on_quit=quit_all,
    )
    bridge = FaceBridge(ActionRouter(handlers), gather)
    host = FaceHost(bridge, webview_module=webview)
    if "--overlay" in sys.argv:
        host.open_overlay()   # the on-screen companion face (transparent, click-through)
    elif "--onboarding" in sys.argv:
        host.open_onboarding()
    else:
        host.open_panel()
    # http_server: serve the bundle over http://127.0.0.1 so CSP 'self' permits it.
    webview.start(http_server=True, debug="--debug" in sys.argv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
