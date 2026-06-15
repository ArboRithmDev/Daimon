"""Overlay process entry (Windows): Qt canvas + TCP server, Qt event loop.

Reuses the shared OverlayServer lifecycle (concurrent accept, live-connection
count, generation-guarded idle quit) by injecting Qt seams — QTimer for the
scheduler, QApplication.quit for terminate, and a queued signal to marshal scene
mutations onto the GUI thread — plus a TCP-loopback listener. Only the transport
and the seams differ from macOS; the anti-multiplication logic is identical.
"""

from __future__ import annotations


def main() -> None:
    import sys

    from PySide6 import QtCore, QtWidgets

    from ...config import load_overlay_config
    from ..launcher_win import _socket_alive
    from ..transport_win import create_server_socket
    from .scene_win import Scene
    from .server import OverlayServer
    from .window_win import make_overlay_canvas

    # Singleton: if another overlay already owns the port, do not open a second.
    if _socket_alive():
        return

    cfg = load_overlay_config()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)

    canvas = make_overlay_canvas(anti_feedback=cfg.anti_feedback, opacity=cfg.opacity)
    scene = Scene(canvas)

    # Marshal arbitrary callables onto the GUI thread via a queued signal. The
    # bridge lives in the GUI thread, so emits from the server's worker threads
    # are delivered as QueuedConnection automatically.
    class _Bridge(QtCore.QObject):
        invoke = QtCore.Signal(object, object)

        def __init__(self):
            super().__init__()
            self.invoke.connect(self._run)

        def _run(self, fn, arg):
            fn(arg)

    bridge = _Bridge()

    def main_dispatch(fn, arg):
        bridge.invoke.emit(fn, arg)

    def scheduler(delay, fn):
        bridge.invoke.emit(lambda _: QtCore.QTimer.singleShot(int(delay * 1000), fn), None)

    def terminate():
        bridge.invoke.emit(lambda _: app.quit(), None)

    OverlayServer(
        scene, flip_height=None,  # Qt is top-left origin like the protocol
        scheduler=scheduler, terminate=terminate, main_dispatch=main_dispatch,
        listener=create_server_socket,
    ).start()

    app.exec()


if __name__ == "__main__":
    main()
