import os
import socket
import sys

import pytest

from daimon.overlay import launcher

# AF_UNIX + fcntl flock are POSIX; the Windows overlay launcher is tested by
# tests/test_overlay_launcher_win.py (TCP + msvcrt lock).
pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX overlay launcher")


def _short_sock(name: str) -> str:
    # AF_UNIX paths are capped (~104 chars on macOS); pytest's tmp_path is too
    # long, so use a short /tmp path keyed to the test + pid.
    return f"/tmp/daimon-test-{name}-{os.getpid()}.sock"


def _release_lock():
    """Drop the module-held singleton flock between assertions/tests."""
    if launcher._lock_fd is not None:
        os.close(launcher._lock_fd)
        launcher._lock_fd = None


def _cleanup(path):
    for p in (path, path + ".lock"):
        try:
            os.unlink(p)
        except OSError:
            pass


def test_bind_singleton_is_exclusive():
    path = _short_sock("excl")
    _release_lock(); _cleanup(path)
    first = launcher.bind_singleton(path)
    assert first is not None, "first caller acquires the socket"
    try:
        # A racing second overlay must NOT acquire it (the flock is held), and
        # must NOT stomp the winner's socket.
        assert launcher.bind_singleton(path) is None
        assert os.path.exists(path), "loser must not touch the winner's socket"
    finally:
        first.close()
        _release_lock()
        _cleanup(path)


def test_bind_singleton_reclaims_stale_socket():
    path = _short_sock("stale")
    _release_lock(); _cleanup(path)
    # A dead overlay leaves a socket node with nothing listening.
    stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stale.bind(path); stale.close()
    assert os.path.exists(path)
    got = launcher.bind_singleton(path)
    assert got is not None, "a stale socket must be reclaimed"
    got.close()
    _release_lock()
    _cleanup(path)


def test_bind_singleton_reacquirable_after_release():
    # When the holder dies (fd closed), the next overlay can acquire the lock.
    path = _short_sock("reacq")
    _release_lock(); _cleanup(path)
    first = launcher.bind_singleton(path)
    assert first is not None
    first.close()
    _release_lock()                      # simulate the holder process exiting
    second = launcher.bind_singleton(path)
    assert second is not None, "lock must be re-acquirable once released"
    second.close()
    _release_lock()
    _cleanup(path)


def test_socket_path_is_env_independent(monkeypatch, tmp_path):
    # The socket path must NOT depend on $TMPDIR — if it did, clients launched
    # with vs without TMPDIR would bind different sockets and run twin overlays.
    monkeypatch.setenv("DAIMON_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("TMPDIR", "/tmp/")
    p1 = launcher.socket_path()
    monkeypatch.setenv("TMPDIR", "/var/folders/xx/T/")
    p2 = launcher.socket_path()
    assert p1 == p2
    assert p1.endswith("overlay.sock")
    assert str(tmp_path) in p1


def test_ensure_running_skips_spawn_when_socket_live(monkeypatch):
    spawned = []
    monkeypatch.setattr(launcher, "_socket_alive", lambda p: True)
    monkeypatch.setattr(launcher, "_spawn", lambda: spawned.append(True))
    launcher.ensure_running()
    assert spawned == []


def test_ensure_running_spawns_when_socket_dead(monkeypatch):
    spawned = []
    monkeypatch.setattr(launcher, "_socket_alive", lambda p: False)
    monkeypatch.setattr(launcher, "_spawn", lambda: spawned.append(True))
    launcher.ensure_running()
    assert spawned == [True]
