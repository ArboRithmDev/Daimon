"""Locate / auto-spawn the long-lived overlay helper process."""

from __future__ import annotations

import os
import socket
import subprocess
import sys


def socket_path() -> str:
    return os.path.join(os.environ.get("TMPDIR", "/tmp"), "daimon-overlay.sock")


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
