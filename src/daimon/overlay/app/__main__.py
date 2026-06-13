"""Overlay process entry: build the window, scene, socket server, run AppKit."""

from __future__ import annotations


def main() -> None:
    from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
    from PyObjCTools import AppHelper
    from ...config import load_overlay_config
    from ..launcher import _socket_alive, socket_path
    from .window import make_overlay_window
    from .scene import Scene
    from .server import OverlayServer

    # Singleton: if another overlay already owns the socket, do not open a
    # second window (that is how orphaned overlays used to pile up).
    if _socket_alive(socket_path()):
        return

    cfg = load_overlay_config()
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)  # no Dock icon
    win = make_overlay_window(anti_feedback=cfg.anti_feedback)
    win.contentView().layer().setOpacity_(cfg.opacity)
    scene = Scene(win.contentView().layer(), height=win.frame().size.height)
    OverlayServer(scene, flip_height=win.frame().size.height).start()
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
