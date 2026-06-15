"""Locate / auto-spawn the long-lived overlay helper process."""

from __future__ import annotations

import fcntl
import os
import socket
import subprocess
import sys

from ..userdata import data_dir

# Held for the overlay process's entire lifetime so the kernel keeps the
# singleton flock; closing this fd (or the process dying) releases the lock.
_lock_fd = None


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
    """Acquire the overlay socket as a singleton, arbitrated by a kernel flock.

    Returns a *listening* socket if this process is the sole overlay, or None if
    another overlay already holds the lock (the caller must then exit).

    A non-blocking exclusive flock on ``<path>.lock`` is the gate: of N racing
    overlays the kernel grants it to exactly one — no bind/unlink/connect dance,
    so no race can leave two overlays alive. Only the lock holder ever touches
    the socket node, so reclaiming a stale socket is safe. The lock releases
    automatically when the holder dies (the fd is closed by the OS).
    """
    global _lock_fd
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
    except OSError:
        pass

    fd = os.open(path + ".lock", os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        os.close(fd)
        return None  # another overlay holds the lock → this one must exit
    _lock_fd = fd    # keep the lock for the life of the process

    # Sole owner: it is now safe to (re)create the socket node unconditionally,
    # clearing any stale file a crashed predecessor left behind.
    try:
        os.unlink(path)
    except OSError:
        pass
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(path)
    s.listen(64)
    return s


def _overlay_cmd() -> list[str]:
    # In the frozen .app, sys.executable is the Daimon binary (NOT python), so
    # `-m daimon.overlay.app` would be ignored and the dispatcher would launch a
    # tray instead. Use the explicit `overlay` subcommand there. From source,
    # sys.executable is python, so go through `-m daimon overlay`.
    if getattr(sys, "frozen", False):
        return [sys.executable, "overlay"]
    return [sys.executable, "-m", "daimon", "overlay"]


def _spawn() -> None:
    # Detached overlay process; it owns the AppKit run loop and the socket.
    subprocess.Popen(
        _overlay_cmd(),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def ensure_running() -> None:
    if not _socket_alive(socket_path()):
        _spawn()
