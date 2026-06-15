"""OverlayClient — fire-and-forget Unix-socket sender.

Never blocks an action and never raises to the caller: if the overlay process
is absent or the pipe breaks, the command is dropped and the socket reset so the
next send retries the connection. Encoding is the pure protocol.encode."""

from __future__ import annotations

import socket

from .protocol import encode


class OverlayClient:
    """Lazily-connecting sender; drops commands rather than block or raise."""

    def __init__(self, socket_path: str, connect_timeout: float = 0.05) -> None:
        self._path = socket_path
        self._timeout = connect_timeout
        self._sock = None

    def _ensure(self) -> None:
        if self._sock is not None:
            return
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.settimeout(self._timeout)
            s.connect(self._path)
            self._sock = s
        except OSError:
            self._sock = None

    def send(self, command) -> None:
        """Encode and push a command; silently reset the socket on any error."""
        self._ensure()
        if self._sock is None:
            return
        try:
            self._sock.sendall(encode(command).encode("utf-8"))
        except OSError:
            old, self._sock = self._sock, None  # reset first → next send reconnects
            try:
                old.close()
            except Exception:
                pass
