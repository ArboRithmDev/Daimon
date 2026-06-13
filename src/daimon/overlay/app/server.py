"""Socket server for the overlay process: reads command lines, applies them to
the Scene on the AppKit main thread.

Lifecycle: the overlay is a long-lived helper, but it must NOT outlive the
client that drives it. The OverlayClient holds one persistent connection for the
life of the MCP-server process, so when that connection drops the consumer is
gone — the server then clears the scene and, unless a new client connects within
a short grace window, terminates the whole overlay process. This is what stops
orphaned overlay windows from lingering after the AI client (or Daimon) quits.

Main-thread dispatch uses PyObjCTools.AppHelper.callAfter (always available
with pyobjc) rather than libdispatch, which requires an extra optional package.
Falls back to a direct apply call if AppHelper is unavailable for any reason.
"""

from __future__ import annotations

import os
import socket
import threading

from ..launcher import socket_path
from ..protocol import Clear, decode

# Seconds with no connected client before the overlay process exits. Short
# enough that ghost windows never outstay the client by much; long enough to
# survive a client reconnecting between commands.
_IDLE_GRACE = 3.0


class OverlayServer:
    def __init__(self, scene, flip_height: float, idle_grace: float = _IDLE_GRACE):
        self._scene = scene
        self._flip = flip_height
        self._grace = idle_grace
        # Bumped on every connect / disconnect; a pending quit timer only fires
        # if its captured generation still matches (i.e. still idle).
        self._quit_gen = 0

    def start(self) -> None:
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        path = socket_path()
        try:
            os.unlink(path)
        except OSError:
            pass
        srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        srv.bind(path); srv.listen(1)
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                continue
            self._client_connected()
            buf = b""
            try:
                with conn:
                    while True:
                        chunk = conn.recv(4096)
                        if not chunk:
                            break
                        buf += chunk
                        while b"\n" in buf:
                            line, buf = buf.split(b"\n", 1)
                            if line.strip():
                                self._dispatch(line.decode("utf-8"))
            except OSError:
                pass
            # Client gone: wipe the scene and arm the idle-quit timer.
            self._client_disconnected()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _client_connected(self) -> None:
        # Cancel any pending quit — a driver is present again.
        self._quit_gen += 1

    def _client_disconnected(self) -> None:
        self._on_main(self._scene.apply, Clear())
        self._arm_quit()

    def _arm_quit(self) -> None:
        """Terminate the overlay process after the idle grace, unless a client
        (re)connects first (which bumps _quit_gen and invalidates this timer)."""
        self._quit_gen += 1
        gen = self._quit_gen

        def _fire():
            if self._quit_gen != gen:
                return  # a client connected in the meantime
            try:
                from AppKit import NSApp
                NSApp().terminate_(None)
            except Exception:
                os._exit(0)

        try:
            from PyObjCTools import AppHelper
            AppHelper.callLater(self._grace, _fire)
        except Exception:
            _fire()

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, line: str) -> None:
        try:
            cmd = decode(line)
        except ValueError:
            return
        # flip Y from global top-left to window bottom-left, then apply on main thread
        flipped = self._flip_cmd(cmd)
        self._on_main(self._scene.apply, flipped)

    def _on_main(self, fn, arg) -> None:
        try:
            from PyObjCTools import AppHelper
            AppHelper.callAfter(fn, arg)
        except Exception:
            fn(arg)

    def _flip_cmd(self, cmd):
        from dataclasses import replace
        if hasattr(cmd, "y"):
            return replace(cmd, y=int(self._flip - cmd.y))
        return cmd
