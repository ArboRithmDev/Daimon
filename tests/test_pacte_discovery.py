import json
import os
import subprocess
from pathlib import Path

import pytest

from daimon.pacte.discovery import discover, Endpoint


def _write(dirp: Path, name: str, **over):
    rec = {"port": 5000, "token": "t", "pid": os.getpid(), "app": "delta", "protocol_version": "1.0"}
    rec.update(over)
    dirp.mkdir(parents=True, exist_ok=True)
    (dirp / name).write_text(json.dumps(rec), encoding="utf-8")
    return dirp / name


def test_discover_none_when_dir_absent(tmp_path):
    assert discover(tmp_path / "nope") is None


def test_discover_returns_endpoint(tmp_path):
    _write(tmp_path, "delta-1.json", port=5050, token="abc", pid=os.getpid())
    ep = discover(tmp_path)
    assert ep == Endpoint(port=5050, token="abc", pid=os.getpid(), app="delta", protocol_version="1.0")


def test_discover_skips_wrong_protocol_version(tmp_path):
    _write(tmp_path, "delta-1.json", protocol_version="0.9")
    assert discover(tmp_path) is None


def test_discover_picks_newest(tmp_path):
    a = _write(tmp_path, "delta-1.json", port=1)
    b = _write(tmp_path, "delta-2.json", port=2)
    os.utime(a, (1, 1))
    os.utime(b, (2, 2))
    assert discover(tmp_path).port == 2


@pytest.mark.skipif(os.name != "posix", reason="os.kill(pid,0) liveness probe is POSIX-only")
def test_discover_rejects_dead_pid(tmp_path):
    """A stale discovery file from an unclean kill carries a dead pid → not discovered."""
    proc = subprocess.Popen(["true"])
    proc.wait()  # exit + reap, so the pid no longer names a live process
    _write(tmp_path, "delta-1.json", pid=proc.pid)
    assert discover(tmp_path) is None


def test_discover_accepts_nonpositive_pid(tmp_path):
    """pid<=0 carries no liveness info (e.g. a test double) → liveness check is skipped."""
    _write(tmp_path, "delta-1.json", pid=0)
    assert discover(tmp_path) is not None


def test_discover_skips_dead_falls_through_to_live(tmp_path):
    """With a dead-pid file and a live-pid file, discover returns the live one."""
    dead = subprocess.Popen(["true"]) if os.name == "posix" else None
    if dead is not None:
        dead.wait()
        d = _write(tmp_path, "delta-dead.json", port=1, pid=dead.pid)
    else:
        d = _write(tmp_path, "delta-dead.json", port=1, pid=0)
    live = _write(tmp_path, "delta-live.json", port=2, pid=os.getpid())
    os.utime(d, (2, 2))   # dead file is NEWEST → must be skipped for the live one
    os.utime(live, (1, 1))
    ep = discover(tmp_path)
    if dead is not None:
        assert ep is not None and ep.port == 2
