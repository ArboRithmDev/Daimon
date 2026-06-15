"""Locate / auto-spawn the long-lived overlay helper process."""

from __future__ import annotations

import os
import socket
import subprocess
import sys

from ..userdata import data_dir


def socket_path() -> str:
    # Must be IDENTICAL for every process that talks to the overlay, regardless
    # of how it was launched. $TMPDIR is NOT — a client started without it lands
    # in /tmp while one with it lands in /var/folders/…, so the two bound
    # different sockets and ran two overlays side by side forever. The per-user
    # data dir is stable and env-independent (the same anchor as config/logs).
    return str(data_dir() / "overlay.sock")


def _socket_alive(path: str) -> bool:
    if not os.path.exists(path):
        return False
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(0.05)
        s.connect(path)
        s.close()
        return True
    except OSError:
        return False


def bind_singleton(path: str):
    """Atomically acquire the overlay socket as a singleton lock.

    Returns a *listening* socket if this process is the sole owner, or None if
    another live overlay already owns the path. The bound socket node IS the
    lock: bind() is an atomic filesystem create, so of N racing overlays exactly
    one wins; the losers see EADDRINUSE, confirm a live owner, and bow out
    WITHOUT unlinking (the old unconditional os.unlink let a loser stomp the
    winner's path, leaving the winner alive but client-less forever).
    """
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except OSError:
        pass
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    try:
        s.bind(path)
    except OSError:
        if _socket_alive(path):
            s.close()
            return None  # a live overlay owns it → caller must exit
        # Stale socket file (previous overlay crashed): reclaim it.
        try:
            os.unlink(path)
        except OSError:
            pass
        try:
            s.bind(path)
        except OSError:
            s.close()
            return None
    s.listen(64)
    return s


def _spawn() -> None:
    # Detached overlay process; it owns the AppKit run loop and the socket.
    subprocess.Popen(
        [sys.executable, "-m", "daimon.overlay.app"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def ensure_running() -> None:
    if not _socket_alive(socket_path()):
        _spawn()
