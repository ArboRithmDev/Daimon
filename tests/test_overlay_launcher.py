import os
import socket

from daimon.overlay import launcher


def _short_sock(name: str) -> str:
    # AF_UNIX paths are capped (~104 chars on macOS); pytest's tmp_path is too
    # long, so use a short /tmp path keyed to the test + pid.
    return f"/tmp/daimon-test-{name}-{os.getpid()}.sock"


def test_bind_singleton_is_exclusive():
    path = _short_sock("excl")
    try:
        os.unlink(path)
    except OSError:
        pass
    first = launcher.bind_singleton(path)
    assert first is not None, "first caller acquires the socket"
    try:
        # A racing second overlay must NOT acquire it, and must NOT unlink it.
        assert launcher.bind_singleton(path) is None
        assert os.path.exists(path), "loser must not stomp the winner's socket"
    finally:
        first.close()
        try:
            os.unlink(path)
        except OSError:
            pass


def test_bind_singleton_reclaims_stale_socket():
    path = _short_sock("stale")
    try:
        os.unlink(path)
    except OSError:
        pass
    # A dead overlay leaves a socket node with nothing listening.
    stale = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    stale.bind(path); stale.close()
    assert os.path.exists(path)
    got = launcher.bind_singleton(path)
    assert got is not None, "a stale socket must be reclaimed"
    got.close()
    os.unlink(path)


def test_socket_path_is_stable_and_in_tmp(monkeypatch):
    monkeypatch.setenv("TMPDIR", "/tmp/")
    assert launcher.socket_path().endswith("daimon-overlay.sock")


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
