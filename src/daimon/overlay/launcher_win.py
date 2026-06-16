"""Locate / auto-spawn the overlay helper process on Windows."""

from __future__ import annotations

import os
import subprocess
import sys

from . import transport_win
from ..userdata import data_dir

# Detach the helper so it outlives the spawning MCP server and shows no console.
_DETACHED_PROCESS = 0x00000008
_CREATE_NEW_PROCESS_GROUP = 0x00000200
_CREATE_NO_WINDOW = 0x08000000

# Held for the overlay process's entire lifetime so the OS keeps the singleton
# lock; closing this fd (or the process dying) releases it.
_lock_fd = None


def socket_path():
    """Endpoint (host, port) — name kept for parity with the macOS launcher."""
    return transport_win.endpoint()


def _socket_alive(_path=None) -> bool:
    return transport_win.is_alive()


def bind_singleton():
    """Acquire the overlay endpoint as a singleton, arbitrated by an exclusive
    file lock (the Windows twin of the macOS flock).

    Returns a *listening* loopback socket if this process is the sole overlay, or
    None if another overlay already holds the lock (the caller must then exit).
    Of N racing overlays the OS grants the lock to exactly one; losers exit
    before opening a window or binding the port, so a twin can never come to
    exist. The lock releases automatically when the holder dies.
    """
    global _lock_fd
    import msvcrt
    import socket

    d = data_dir()
    try:
        d.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    lock_path = d / "overlay.lock"

    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
    try:
        # Non-blocking exclusive lock on one byte (locking past EOF is allowed).
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
    except OSError:
        os.close(fd)
        return None  # another overlay holds the lock → this one must exit
    _lock_fd = fd  # hold for the life of the process

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((transport_win._HOST, transport_win._PORT))  # no SO_REUSEADDR — sole owner via the lock
    s.listen(64)
    return s


def _overlay_cmd() -> list[str]:
    # In the frozen exe, sys.executable is the Daimon binary (NOT python), so
    # `-m daimon.overlay.app` would be ignored and the dispatcher would launch a
    # TRAY instead (piling up duplicate resident Daimons). Use the explicit
    # `overlay` subcommand there. From source, go through `-m daimon overlay`.
    if getattr(sys, "frozen", False):
        return [sys.executable, "overlay"]
    return [sys.executable, "-m", "daimon", "overlay"]


def _spawn() -> None:
    subprocess.Popen(
        _overlay_cmd(),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        creationflags=_DETACHED_PROCESS | _CREATE_NEW_PROCESS_GROUP | _CREATE_NO_WINDOW,
    )


def ensure_running() -> None:
    if not transport_win.is_alive():
        _spawn()


def make_client():
    """An OverlayClient bound to this launcher's endpoint (Windows, TCP)."""
    from .client_win import OverlayClient
    return OverlayClient()
