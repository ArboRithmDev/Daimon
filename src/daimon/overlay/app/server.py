"""Socket server for the overlay process: reads command lines, applies them to
the Scene on the AppKit main thread.

Concurrency & lifecycle. The overlay is a single shared helper that may be
driven by several MCP-server processes at once (one OverlayClient connection
each, held for the life of that process). The server therefore:

* keeps an accept loop running permanently and handles every connection in its
  own thread — so a long-lived connection can never wedge `accept()` (the old
  single-connection design did, which made liveness probes fail and the
  launcher spawn duplicate overlays that piled up as orphans);
* counts live connections, and when the count falls to zero clears the scene
  and — unless a client reconnects within a short grace — terminates the whole
  process, so no overlay window outlives its drivers.

Main-thread dispatch uses PyObjCTools.AppHelper.callAfter (always available
with pyobjc) rather than libdispatch, which requires an extra optional package.
Falls back to a direct apply call if AppHelper is unavailable for any reason.
"""

from __future__ import annotations

import os
import threading

from ..protocol import Clear, decode

# Seconds with no connected client before the overlay process exits. Short
# enough that ghost windows never outstay the client by much; long enough to
# survive a client reconnecting between commands.
_IDLE_GRACE = 3.0
# A spawned overlay that never gets a single client (e.g. the loser of a spawn
# race, or a spawn whose driver vanished before sending) reaps itself after
# this longer startup window.
_STARTUP_GRACE = 60.0


class OverlayServer:
    """Accepts client connections, applies commands to the Scene, self-reaps idle."""
    def __init__(self, scene, flip_height: float, idle_grace: float = _IDLE_GRACE,
                 *, listen_sock=None, startup_grace: float = _STARTUP_GRACE,
                 scheduler=None, terminate=None, main_dispatch=None):
        self._scene = scene
        # flip_height=None disables the Y flip (Windows/Qt is top-left origin like
        # the protocol; macOS passes the window height to flip to bottom-left).
        self._flip = flip_height
        self._grace = idle_grace
        self._startup_grace = startup_grace
        self._sock = listen_sock
        self._lock = threading.Lock()
        self._clients = 0
        # Bumped whenever the client count changes; a pending quit timer only
        # fires if its captured generation still matches (i.e. still idle).
        self._quit_gen = 0
        # Injectable seams (tests / Windows). Defaults wire to the AppKit run
        # loop / NSApp / a Unix-domain listener.
        self._scheduler = scheduler            # (delay, fn) -> None
        self._terminate = terminate            # () -> None
        self._main_dispatch = main_dispatch    # (fn, arg) -> None

    def start(self) -> None:
        """Launch the accept loop on a daemon thread."""
        threading.Thread(target=self._serve, daemon=True).start()

    def _serve(self) -> None:
        srv = self._sock
        if srv is None:
            return  # no socket acquired → nothing to serve
        # Reap ourselves if no client ever connects (lost a spawn race, etc.).
        self._arm_quit(self._startup_grace)
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                continue
            threading.Thread(target=self._handle, args=(conn,), daemon=True).start()

    def _handle(self, conn) -> None:
        self._client_added()
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
        finally:
            self._client_removed()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _client_added(self) -> None:
        with self._lock:
            self._clients += 1
            self._quit_gen += 1  # cancel any pending idle quit

    def _client_removed(self) -> None:
        with self._lock:
            self._clients = max(0, self._clients - 1)
            idle = self._clients == 0
        if idle:
            # No drivers left: clear the scene and arm the idle-quit timer.
            self._on_main(self._scene.apply, Clear())
            self._arm_quit()

    def _arm_quit(self, grace=None) -> None:
        with self._lock:
            self._quit_gen += 1
            gen = self._quit_gen

        def _fire():
            with self._lock:
                stale = self._quit_gen != gen or self._clients > 0
            if stale:
                return  # a client connected in the meantime
            self._do_terminate()

        self._schedule(self._grace if grace is None else grace, _fire)

    def _schedule(self, delay, fn) -> None:
        if self._scheduler is not None:
            self._scheduler(delay, fn)
            return
        try:
            from PyObjCTools import AppHelper
            AppHelper.callLater(delay, fn)
        except Exception:
            fn()

    def _do_terminate(self) -> None:
        if self._terminate is not None:
            self._terminate()
            return
        try:
            from AppKit import NSApp
            NSApp().terminate_(None)
        except Exception:
            os._exit(0)

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
        if self._main_dispatch is not None:
            self._main_dispatch(fn, arg)
            return
        try:
            from PyObjCTools import AppHelper
            AppHelper.callAfter(fn, arg)
        except Exception:
            fn(arg)

    def _flip_cmd(self, cmd):
        from dataclasses import replace
        if self._flip is not None and hasattr(cmd, "y"):
            return replace(cmd, y=int(self._flip - cmd.y))
        return cmd
