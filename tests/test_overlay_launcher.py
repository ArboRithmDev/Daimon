from daimon.overlay import launcher


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
