"""Locate / auto-spawn the overlay helper process on Windows."""

from __future__ import annotations

import subprocess
import sys

from .transport_win import endpoint, is_alive

# Detach the helper so it outlives the spawning MCP server and shows no console.
_DETACHED_PROCESS = 0x00000008
_CREATE_NEW_PROCESS_GROUP = 0x00000200
_CREATE_NO_WINDOW = 0x08000000


def socket_path():
    """Endpoint (host, port) — name kept for parity with the macOS launcher."""
    return endpoint()


def _socket_alive(_path=None) -> bool:
    return is_alive()


def _spawn() -> None:
    subprocess.Popen(
        [sys.executable, "-m", "daimon.overlay.app"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=_DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP | _CREATE_NO_WINDOW,
    )


def ensure_running() -> None:
    if not is_alive():
        _spawn()


def make_client():
    """An OverlayClient bound to this launcher's endpoint (Windows, TCP)."""
    from .client_win import OverlayClient
    return OverlayClient()
