"""Download an update asset over HTTPS and verify its SHA256.

Integrity is the gate before any apply: Daimon sees and acts on the machine, so
a tampered or corrupted asset must never be executed. A hash mismatch deletes the
file and raises — there is no "apply anyway" path.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK = 1 << 16  # 64 KiB


class IntegrityError(Exception):
    """The downloaded asset's SHA256 did not match the manifest."""


def sha256_of(path) -> str:
    """Hex SHA256 of a file, streamed."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def download(url: str, dest, *, timeout: float = 60.0) -> Path:
    """Stream an HTTPS URL to ``dest``. HTTPS is enforced."""
    import urllib.request

    if not url.lower().startswith("https://"):
        raise ValueError("download URL must be HTTPS")
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as resp, open(dest, "wb") as f:  # noqa: S310
        while True:
            chunk = resp.read(_CHUNK)
            if not chunk:
                break
            f.write(chunk)
    return dest


def download_verified(url: str, sha256: str, dest, *, timeout: float = 60.0) -> Path:
    """Download then verify SHA256. On mismatch: delete the file and raise
    IntegrityError. Returns the verified file path."""
    path = download(url, dest, timeout=timeout)
    actual = sha256_of(path)
    if actual.lower() != str(sha256).lower():
        try:
            path.unlink()
        except OSError:
            pass
        raise IntegrityError(f"SHA256 mismatch: expected {sha256}, got {actual}")
    return path
