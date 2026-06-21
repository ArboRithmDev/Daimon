"""Integrated tray: the menu-bar glyph opens the webview panel.

pywebview owns the NSApplication run loop; the NSStatusItem is installed on the
SAME shared NSApplication, so they cohabit. The glyph click toggles the panel
(anchored under the glyph); clicking away dismisses it. Run: `python -m daimon.face.tray`.
"""

from __future__ import annotations

from pathlib import Path

# Keep ObjC targets / status items alive for the process lifetime.
_KEEP: list = []


def _set_glyph(btn) -> None:
    from AppKit import NSImage
    from Foundation import NSSize

    assets = Path(__file__).resolve().parents[1] / "assets"
    for name in ("menubar-glyph@2x.png", "menubar-glyph.png"):
        p = assets / name
        if p.exists():
            img = NSImage.alloc().initWithContentsOfFile_(str(p))
            if img is not None:
                img.setSize_(NSSize(18, 18))
                img.setTemplate_(True)  # macOS tints it to the menu bar
                btn.setImage_(img)
                btn.setTitle_("")
                return
    btn.setTitle_("δ")


def run() -> int:
    import webview
    from AppKit import (
        NSApplication, NSApplicationActivationPolicyAccessory, NSStatusBar,
    )

    from .bridge import FaceBridge
    from .host import FaceHost
    from .native import confirm_l4, open_onboarding
    from .platform import get_adapter
    from ..objc_bridge import make_target
    from ..tray.actions import ActionRouter
    from ..tray.actions_impl import TrayActions
    from ..tray.state import gather

    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)  # no Dock icon

    adapter = get_adapter()
    holder: dict = {}

    def push():
        host = holder.get("host")
        if host is not None:
            host.push_state()

    handlers = TrayActions(
        on_change=push,
        confirm_l4=confirm_l4,
        open_onboarding=open_onboarding,
        on_quit=lambda: app.terminate_(None),
    )
    host = FaceHost(FaceBridge(ActionRouter(handlers), gather), webview_module=webview, adapter=adapter)
    holder["host"] = host
    panel = host.open_panel(hidden=True)

    bar = NSStatusBar.systemStatusBar()
    status_item = bar.statusItemWithLength_(-1)
    btn = status_item.button()
    if btn is not None:
        _set_glyph(btn)

    state = {"visible": False}

    import threading

    def toggle():
        if state["visible"]:
            panel.hide()
            state["visible"] = False
        else:
            adapter.anchor_under_statusitem(panel, status_item)  # main thread (AppKit)
            panel.show()
            # push_state runs evaluate_js, which must NOT run on the main thread:
            # WKWebView evaluates JS on the main run loop, so calling it here would
            # deadlock (freeze the whole app). Refresh from a worker thread.
            threading.Thread(target=host.push_state, daemon=True).start()
            state["visible"] = True

    target = make_target(toggle)
    if btn is not None:
        btn.setTarget_(target)
        btn.setAction_("invoke:")
    _KEEP.extend([status_item, target])

    # Dismiss-on-blur: a click outside the panel (and not on the glyph) closes it.
    def dismiss():
        if state["visible"]:
            panel.hide()
            state["visible"] = False

    monitor = adapter.watch_outside_click(panel, status_item, dismiss)
    if monitor is not None:
        _KEEP.append(monitor)

    # Re-assert accessory policy after pywebview's own app setup, then run.
    def _after():
        app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    webview.start(_after)
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
