"""Fetch the update manifest over HTTPS. Network I/O is isolated here so the
decision core stays pure and testable."""

from __future__ import annotations


def fetch_manifest(url: str, *, timeout: float = 10.0) -> dict:
    """GET the ``latest.json`` manifest. HTTPS is enforced — Daimon sees and acts
    on the machine, so the update channel must not be downgradeable to plain HTTP."""
    import json
    import urllib.request

    if not url.lower().startswith("https://"):
        raise ValueError("update manifest URL must be HTTPS")
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 — HTTPS enforced above
        data = json.loads(resp.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("update manifest is not a JSON object")
    return data
