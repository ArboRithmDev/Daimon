"""Socket server for the overlay process: reads command lines, applies them to
the Scene on the AppKit main thread.

Main-thread dispatch uses PyObjCTools.AppHelper.callAfter (always available
with pyobjc) rather than libdispatch, which requires an extra optional package.
Falls back to a direct apply call if AppHelper is unavailable for any reason.
"""

from __future__ import annotations

import os
import socket
import threading

from ..launcher import socket_path
from ..protocol import decode


class OverlayServer:
    def __init__(self, scene, flip_height: float):
        self._scene = scene
        self._flip = flip_height

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
            conn, _ = srv.accept()
            buf = b""
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

    def _dispatch(self, line: str) -> None:
        try:
            cmd = decode(line)
        except ValueError:
            return
        # flip Y from global top-left to window bottom-left, then apply on main thread
        flipped = self._flip_cmd(cmd)
        try:
            from PyObjCTools import AppHelper
            AppHelper.callAfter(self._scene.apply, flipped)
        except Exception:
            self._scene.apply(flipped)

    def _flip_cmd(self, cmd):
        from dataclasses import replace
        if hasattr(cmd, "y"):
            return replace(cmd, y=int(self._flip - cmd.y))
        return cmd
