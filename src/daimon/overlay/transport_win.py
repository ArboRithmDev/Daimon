"""Overlay transport for Windows — loopback TCP on an ephemeral port.

Python's AF_UNIX support is unreliable on Windows, so the overlay runs over a
loopback socket. A FIXED port is a trap: Windows reserves blocks of the dynamic
range (Hyper-V / WSL), and binding inside one fails with WSAEACCES (WinError
10013). So the overlay binds port 0 — the kernel hands out a free port that is
never in a reserved range and never already taken — and writes it to
``overlay.port`` in the per-user data dir. Every client reads the port from that
file, so they all rendezvous without a hard-coded number.
"""

from __future__ import annotations

import socket

from ..userdata import data_dir

_HOST = "127.0.0.1"


def _port_file():
    return data_dir() / "overlay.port"


def write_port(port: int) -> None:
    """Publish the port the overlay bound, for clients to read. Best-effort."""
    try:
        p = _port_file()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(port), encoding="utf-8")
    except OSError:
        pass


def read_port():
    """The port the overlay published, or None if absent/unreadable."""
    try:
        return int(_port_file().read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return None


def endpoint():
    return (_HOST, read_port())


def connect(timeout: float = 0.05) -> socket.socket:
    """Connect to the overlay helper; raises OSError if it is not running."""
    port = read_port()
    if not port:
        raise OSError("overlay port file missing")
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect((_HOST, port))
    return s


def is_alive(timeout: float = 0.05) -> bool:
    try:
        connect(timeout).close()
        return True
    except OSError:
        return False
