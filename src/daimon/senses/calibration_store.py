"""Persistence for calibration profiles — the per-OS data-dir store.

Profiles live in a single JSON file under the writable data dir
(`<data>/config/calibration.json`), shared across the tray, onboarding and MCP
processes exactly like the other live config. Reuses the W4 `userdata` helper so
the location is `%APPDATA%` / `~/Library` / XDG per OS.

Writes follow the config doctrine, identical to the client-registration path:
- **atomic**: write a `.tmp` then `os.replace` (never a half-written file);
- **backed-up**: the previous file is copied to `calibration.json.bak.<ts>`
  before being overwritten (reversible);
- **idempotent / upsert**: saving a profile name that already exists replaces it
  in place rather than duplicating, so re-calibrating an environment is safe.

`FakeProfileStore` is the in-memory twin so the tools and boot auto-match can be
tested without touching the disk.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from ..userdata import config_dir
from .calibration import (
    PROFILE_SCHEMA_VERSION,
    EnvironmentProfile,
    match_profile,
)


def profiles_path() -> Path:
    """Path to the calibration store inside the per-OS data dir."""
    return config_dir() / "calibration.json"


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


class ProfileStore:
    """Disk-backed calibration profile store (atomic, backed-up, idempotent)."""

    def __init__(self, path: Path | None = None) -> None:
        # Resolved lazily-by-default so $DAIMON_DATA_DIR set after import (tests)
        # is honoured; pass an explicit path to pin it.
        self._path = path

    @property
    def path(self) -> Path:
        return self._path or profiles_path()

    def load_all(self) -> list[EnvironmentProfile]:
        """Load every saved profile; a missing/empty file yields []."""
        path = self.path
        if not path.exists():
            return []
        raw = json.loads(path.read_text(encoding="utf-8") or "{}")
        return [EnvironmentProfile.from_dict(d) for d in raw.get("profiles", [])]

    def save(self, profile: EnvironmentProfile) -> None:
        """Upsert a profile by name; atomic write with a timestamped backup."""
        profiles = [p for p in self.load_all() if p.name != profile.name]
        profiles.append(profile)
        self._write_all(profiles)

    def match(self, displays) -> EnvironmentProfile | None:
        """Auto-match the active topology against the saved profiles (or None)."""
        return match_profile(self.load_all(), displays)

    def _write_all(self, profiles: list[EnvironmentProfile]) -> None:
        path = self.path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            path.with_name(f"{path.name}.bak.{_ts()}").write_text(
                path.read_text(encoding="utf-8"), encoding="utf-8")
        data = {
            "version": PROFILE_SCHEMA_VERSION,
            "profiles": [p.to_dict() for p in profiles],
        }
        tmp = path.with_name(f"{path.name}.tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")
        os.replace(tmp, path)


class FakeProfileStore:
    """In-memory profile store twin — same surface as ProfileStore, no disk."""

    def __init__(self) -> None:
        self._by_name: dict[str, EnvironmentProfile] = {}

    def load_all(self) -> list[EnvironmentProfile]:
        return list(self._by_name.values())

    def save(self, profile: EnvironmentProfile) -> None:
        self._by_name[profile.name] = profile  # upsert by name

    def match(self, displays) -> EnvironmentProfile | None:
        return match_profile(self.load_all(), displays)
