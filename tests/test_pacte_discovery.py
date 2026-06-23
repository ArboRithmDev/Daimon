import json
from pathlib import Path
from daimon.pacte.discovery import discover, Endpoint


def _write(dirp: Path, name: str, **over):
    rec = {"port": 5000, "token": "t", "pid": 1, "app": "delta", "protocol_version": "1.0"}
    rec.update(over)
    dirp.mkdir(parents=True, exist_ok=True)
    (dirp / name).write_text(json.dumps(rec), encoding="utf-8")
    return dirp / name


def test_discover_none_when_dir_absent(tmp_path):
    assert discover(tmp_path / "nope") is None


def test_discover_returns_endpoint(tmp_path):
    _write(tmp_path, "delta-1.json", port=5050, token="abc", pid=42)
    ep = discover(tmp_path)
    assert ep == Endpoint(port=5050, token="abc", pid=42, app="delta", protocol_version="1.0")


def test_discover_skips_wrong_protocol_version(tmp_path):
    _write(tmp_path, "delta-1.json", protocol_version="0.9")
    assert discover(tmp_path) is None


def test_discover_picks_newest(tmp_path):
    import os
    a = _write(tmp_path, "delta-1.json", port=1)
    b = _write(tmp_path, "delta-2.json", port=2)
    os.utime(a, (1, 1))
    os.utime(b, (2, 2))
    assert discover(tmp_path).port == 2
