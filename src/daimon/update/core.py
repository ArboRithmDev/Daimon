"""Pure update logic: version compare + asset selection. No OS or network I/O.

Manifest shape (``latest.json`` attached to the GitHub release)::

    {
      "version": "0.0.8",
      "notes": "…",
      "min_os": {"win64": "10.0.19041", "macos": "11.0"},
      "assets": {
        "win64": {"url": "https://…/Daimon-0.0.8-setup.exe", "sha256": "…"},
        "macos": {"url": "https://…/Daimon-0.0.8.dmg",       "sha256": "…"}
      }
    }
"""

from __future__ import annotations

import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class UpdateInfo:
    """A resolved, applicable update for the current platform."""
    version: str
    url: str
    sha256: str
    notes: str = ""


def parse_version(s: str) -> tuple[tuple[int, ...], tuple[str, ...]]:
    """('v0.0.8-beta.1') -> ((0, 0, 8), ('beta', '1')); release-only -> ((0,0,8), ())."""
    s = s.strip().lstrip("vV")
    core, _, pre = s.partition("-")
    rel = tuple(int(x) for x in core.split(".") if x != "")
    pre_t = tuple(pre.split(".")) if pre else ()
    return rel, pre_t


def _key(parsed):
    rel, pre = parsed
    # A final release ranks ABOVE any prerelease of the same release
    # (0.0.8 > 0.0.8-beta); prereleases compare lexically among themselves.
    return (rel, 0 if pre else 1, pre)


def is_newer(latest: str, current: str, *, allow_prerelease: bool = False) -> bool:
    """True if ``latest`` is strictly newer than ``current``. Prereleases are
    ignored unless ``allow_prerelease`` (a stable build never auto-offers a beta)."""
    pl, pc = parse_version(latest), parse_version(current)
    if pl[1] and not allow_prerelease:
        return False
    return _key(pl) > _key(pc)


def platform_key() -> str:
    """Manifest asset key for the running OS."""
    if sys.platform == "win32":
        return "win64"
    if sys.platform == "darwin":
        return "macos"
    return sys.platform


def select_asset(manifest: dict, key: str) -> dict | None:
    """The asset entry for *key*, or None if absent/incomplete."""
    asset = (manifest.get("assets") or {}).get(key)
    if not isinstance(asset, dict) or not asset.get("url") or not asset.get("sha256"):
        return None
    return asset


def decide(manifest: dict, current_version: str, *,
           allow_prerelease: bool = False, key: str | None = None) -> UpdateInfo | None:
    """Resolve an applicable update from a manifest, or None if up to date / no
    asset for this platform."""
    version = manifest.get("version")
    if not version or not is_newer(version, current_version, allow_prerelease=allow_prerelease):
        return None
    asset = select_asset(manifest, key or platform_key())
    if asset is None:
        return None
    return UpdateInfo(version=str(version), url=asset["url"], sha256=asset["sha256"],
                      notes=str(manifest.get("notes", "")))
