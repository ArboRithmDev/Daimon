"""Service layer for the UI: ties config + current version + check/apply.

Kept thin and side-effecting; the decision logic stays in the pure core.
"""

from __future__ import annotations

from .core import UpdateInfo


def current_version() -> str:
    """The running build's version (read from the bundle/metadata)."""
    from .. import __version__
    return __version__


def check_for_update(cfg=None) -> UpdateInfo | None:
    """Fetch the manifest and decide. Returns None if disabled / up to date /
    no asset for this platform. Raises on network/manifest errors (caller logs)."""
    from ..config import load_update_config
    from . import check
    cfg = cfg or load_update_config()
    if not cfg.enabled:
        return None
    return check(cfg.manifest_url, current_version(), allow_prerelease=cfg.allow_prerelease)


def apply_update(info: UpdateInfo) -> None:
    """Download+verify then hand off to the OS apply adapter (caller quits after)."""
    from . import apply
    apply(info)
