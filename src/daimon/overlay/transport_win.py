"""Overlay transport for Windows — TCP loopback.

Python's AF_UNIX support is unreliable on Windows, so the overlay's single-helper
socket runs on a fixed loopback port instead. Same line-delimited JSON protocol;
only the rendezvous changes. The port is process-agnostic so the launcher, the
client (every MCP server), and the overlay helper all find the same endpoint.
"""

from __future__ import annotations

import socket

_HOST = "127.0.0.1"
# Fixed rendezvous port for the Daimon overlay helper (single-user, single-host).
_PORT = 49737


def endpoint() -> tuple[str, int]:
    return (_HOST, _PORT)


def create_server_socket() -> socket.socket:
    """A bound, listening loopback socket for the overlay helper."""
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((_HOST, _PORT))
    srv.listen(64)
    return srv


def connect(timeout: float = 0.05) -> socket.socket:
    """Connect to the overlay helper; raises OSError if it is not running."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((_HOST, _PORT))
    return s


def is_alive(timeout: float = 0.05) -> bool:
    try:
        connect(timeout).close()
        return True
    except OSError:
        return False
