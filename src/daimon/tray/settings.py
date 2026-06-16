"""Write the settings the menu can change (motor ceiling, overlay on/off).

Atomic + backup + key-preserving. The ceiling is clamped to VALIDATION — L4
never comes from a menu click (it needs written consent via the control CLI)."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from ..motor.types import Level


def _read(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}
    data = yaml.safe_load(text)
    return data if isinstance(data, dict) else {}


def _write(path: Path, data: dict, ts: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        path.with_name(f"{path.name}.bak.{ts}").write_text(
            path.read_text(encoding="utf-8"), encoding="utf-8")
    tmp = path.with_name(f"{path.name}.tmp")
    tmp.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")
    os.replace(tmp, path)


def _ts() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def set_ceiling(name: str, path: Path) -> None:
    """Persist the motor ceiling, clamped to VALIDATION so a menu can't reach L4."""
    try:
        level = Level[name.strip().upper()]
    except KeyError:
        return
    if level > Level.VALIDATION:        # never L4 from a menu
        level = Level.VALIDATION
    data = _read(path)
    motor = data.setdefault("motor", {})
    if not isinstance(motor, dict):
        motor = {}
        data["motor"] = motor
    motor["ceiling"] = level.name
    _write(path, data, _ts())


def set_overlay(enabled: bool, path: Path) -> None:
    """Persist the overlay on/off toggle, preserving other keys in the config."""
    data = _read(path)
    overlay = data.setdefault("overlay", {})
    if not isinstance(overlay, dict):
        overlay = {}
        data["overlay"] = overlay
    overlay["enabled"] = bool(enabled)
    _write(path, data, _ts())
