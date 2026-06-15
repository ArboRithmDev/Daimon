"""Overlay process entry: build the window, scene, socket server, run AppKit."""

from __future__ import annotations


def main() -> None:
    """Acquire the singleton socket, build the window/scene/server, run AppKit."""
    from AppKit import NSApplication, NSApplicationActivationPolicyAccessory
    from PyObjCTools import AppHelper
    from ...config import load_overlay_config
    from ..launcher import bind_singleton, socket_path
    from .window import make_overlay_window
    from .scene import Scene
    from .server import OverlayServer

    # Acquire the socket FIRST, atomically. If another overlay already owns it
    # we exit immediately — before opening any window — so racing spawns can no
    # longer leave a second, client-less overlay running forever.
    sock = bind_singleton(socket_path())
    if sock is None:
        return

    cfg = load_overlay_config()
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)  # no Dock icon
    win = make_overlay_window(anti_feedback=cfg.anti_feedback)
    win.contentView().layer().setOpacity_(cfg.opacity)
    scene = Scene(win.contentView().layer(), height=win.frame().size.height)
    OverlayServer(scene, flip_height=win.frame().size.height, listen_sock=sock).start()
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
