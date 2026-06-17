"""Download + SHA256 integrity gate — run on every platform (download mocked)."""

import hashlib

import pytest

from daimon.update import download as dl


def test_sha256_of_matches_hashlib(tmp_path):
    p = tmp_path / "blob"
    p.write_bytes(b"daimon-update-bytes")
    assert dl.sha256_of(p) == hashlib.sha256(b"daimon-update-bytes").hexdigest()


def test_download_rejects_non_https(tmp_path):
    with pytest.raises(ValueError):
        dl.download("http://insecure/x", tmp_path / "x")


def _fake_download(content: bytes):
    def _dl(url, dest, *, timeout=60.0):
        from pathlib import Path
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(content)
        return dest
    return _dl


def test_download_verified_ok(monkeypatch, tmp_path):
    content = b"the new bundle"
    monkeypatch.setattr(dl, "download", _fake_download(content))
    digest = hashlib.sha256(content).hexdigest()
    out = dl.download_verified("https://r/asset", digest, tmp_path / "asset")
    assert out.exists() and out.read_bytes() == content


def test_download_verified_rejects_tampered_asset(monkeypatch, tmp_path):
    monkeypatch.setattr(dl, "download", _fake_download(b"tampered"))
    dest = tmp_path / "asset"
    with pytest.raises(dl.IntegrityError):
        dl.download_verified("https://r/asset", "0" * 64, dest)
    assert not dest.exists()   # mismatched file is deleted, never left to run
