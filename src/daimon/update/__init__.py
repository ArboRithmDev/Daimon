"""Daimon self-update.

OS-agnostic decision core (``core``) + a network-isolated manifest fetcher
(``source``) + per-platform apply adapters (later phases). The update replaces
the whole frozen bundle (installer / .app), not a sub-package — Daimon ships as
one PyInstaller bundle, unlike SecondBrain's swappable pip engine.

Integrity is mandatory: nothing is applied without verifying the asset's SHA256
against the release manifest (a tool that sees and acts on the machine never
pulls unverified code).
"""

from __future__ import annotations

from .core import UpdateInfo, decide, is_newer, parse_version, platform_key

__all__ = ["UpdateInfo", "decide", "is_newer", "parse_version", "platform_key",
           "check", "apply"]


def check(manifest_url: str, current_version: str, *, allow_prerelease: bool = False):
    """Fetch the manifest and decide if an update applies. Returns UpdateInfo|None."""
    from .source import fetch_manifest
    return decide(fetch_manifest(manifest_url), current_version,
                  allow_prerelease=allow_prerelease)


def apply(info: UpdateInfo, *, install_dir=None) -> None:
    """Download+verify the asset and hand off to the platform apply adapter.
    The caller quits afterward so its files unlock for the replace."""
    from .apply import run
    run(info, install_dir=install_dir)
