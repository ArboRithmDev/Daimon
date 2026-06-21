"""Apply a resolved update: download + verify the asset, then hand off to the
platform adapter. The caller (the tray) quits after this returns so its files
unlock for the replace."""

from __future__ import annotations

import sys
from pathlib import Path

from .core import UpdateInfo
from .download import download_verified


def staging_path(info: UpdateInfo) -> Path:
    """Where the verified asset is downloaded (per-user data dir)."""
    from ..userdata import data_dir
    name = info.url.rsplit("/", 1)[-1] or "daimon-update"
    d = data_dir() / "updates"
    d.mkdir(parents=True, exist_ok=True)
    return d / name


def run(info: UpdateInfo, *, install_dir=None) -> None:
    """Download+verify the asset, then dispatch to the OS apply adapter."""
    install_dir = Path(install_dir) if install_dir else Path(sys.executable).parent
    asset = download_verified(info.url, info.sha256, staging_path(info))
    if sys.platform == "win32":
        from . import apply_win
        apply_win.apply(asset, install_dir)
    elif sys.platform == "darwin":
        from . import apply_macos
        apply_macos.apply(asset, install_dir)
    else:
        raise NotImplementedError(f"update apply not supported on {sys.platform}")
