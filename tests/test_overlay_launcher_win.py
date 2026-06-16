"""Windows overlay launcher — exclusive singleton + frozen-aware spawn. Win-only."""

import socket
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows-only launcher")


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_bind_singleton_is_exclusive(monkeypatch, tmp_path):
    monkeypatch.setenv("DAIMON_DATA_DIR", str(tmp_path))
    from daimon.overlay import launcher_win, transport_win

    monkeypatch.setattr(transport_win, "_PORT", _free_port())
    monkeypatch.setattr(launcher_win, "_lock_fd", None, raising=False)

    s1 = launcher_win.bind_singleton()
    assert s1 is not None  # sole owner
    try:
        s2 = launcher_win.bind_singleton()
        assert s2 is None  # lock held → loser must back off
    finally:
        s1.close()
        import os
        if launcher_win._lock_fd is not None:
            os.close(launcher_win._lock_fd)
            launcher_win._lock_fd = None


def test_overlay_cmd_is_frozen_aware(monkeypatch):
    from daimon.overlay import launcher_win

    monkeypatch.setattr(launcher_win.sys, "frozen", True, raising=False)
    monkeypatch.setattr(launcher_win.sys, "executable", r"C:\Program Files\Daimon\Daimon.exe")
    # Frozen: address the dispatcher subcommand, NEVER `-m` (sys.executable is the
    # Daimon binary, not python — `-m` would launch a tray).
    assert launcher_win._overlay_cmd() == [r"C:\Program Files\Daimon\Daimon.exe", "overlay"]
    assert "-m" not in launcher_win._overlay_cmd()

    monkeypatch.setattr(launcher_win.sys, "frozen", False, raising=False)
    monkeypatch.setattr(launcher_win.sys, "executable", r"C:\Python313\python.exe")
    assert launcher_win._overlay_cmd() == [r"C:\Python313\python.exe", "-m", "daimon", "overlay"]
