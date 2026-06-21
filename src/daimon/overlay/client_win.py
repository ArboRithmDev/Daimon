"""OverlayClient (Windows) — fire-and-forget TCP-loopback sender.

Same contract as the macOS ``OverlayClient``: never blocks an action, never
raises to the caller. If the overlay helper is absent or the pipe breaks, the
command is dropped and the socket reset so the next send retries. Encoding is
the shared pure ``protocol.encode``.
"""

from __future__ import annotations

from .protocol import encode


class OverlayClient:
    def __init__(self, address=None, connect_timeout: float = 0.05) -> None:
        # address kept for signature parity; the endpoint is fixed (transport_win).
        self._timeout = connect_timeout
        self._sock = None

    def _ensure(self) -> None:
        if self._sock is not None:
            return
        try:
            from .transport_win import connect
            self._sock = connect(self._timeout)
        except OSError:
            self._sock = None

    def send(self, command) -> None:
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
