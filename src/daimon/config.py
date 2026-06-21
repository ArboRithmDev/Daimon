"""Configuration loading for Daimon.

The only config that matters at this stage is the set of *exclusion zones* —
the secrets filter that must exist from day one (locked decision). It is loaded
once and handed to every sense, so the redaction layer is common to Vue and
Touché alike.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .userdata import config_dir

# Resolution order for the exclusion config:
#   1. $DAIMON_CONFIG (explicit override)
#   2. <user data>/config/exclusions.yaml (writable; shared across processes)
#   3. ./config/exclusions.example.yaml (committed template, empty filter)
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CONFIG = config_dir() / "exclusions.yaml"
_EXAMPLE_CONFIG = _REPO_ROOT / "config" / "exclusions.example.yaml"


@dataclass(frozen=True)
class Rect:
    """A screen rectangle to redact, in global display points."""

    x: int
    y: int
    width: int
    height: int


_DEFAULT_SECRET_ROLES = ("AXSecureTextField",)


@dataclass(frozen=True)
class ExclusionConfig:
    """Declarative exclusion zones. Anything matching is hidden before serving.

    - apps:           bundle identifiers whose windows must never be perceived
                      (e.g. "com.1password.1password"). Frontmost match => the
                      whole snapshot is refused.
    - window_titles:  regex patterns; matching windows are redacted.
    - regions:        fixed screen rectangles always blacked out.
    - secret_roles:   AX roles whose value must be blanked (e.g. AXSecureTextField).
    - secret_apps:    bundle IDs whose content is always treated as secret.
    """

    apps: tuple[str, ...] = ()
    window_titles: tuple[str, ...] = ()
    regions: tuple[Rect, ...] = ()
    secret_roles: tuple[str, ...] = _DEFAULT_SECRET_ROLES
    secret_apps: tuple[str, ...] = ()


@dataclass(frozen=True)
class Config:
    """Top-level Daimon config; for now just the exclusion zones."""

    exclusions: ExclusionConfig = field(default_factory=ExclusionConfig)


def _config_path() -> Path:
    """Resolve the exclusion config path (env > user data > example)."""
    env = os.environ.get("DAIMON_CONFIG")
    if env:
        return Path(env).expanduser()
    if _DEFAULT_CONFIG.exists():
        return _DEFAULT_CONFIG
    return _EXAMPLE_CONFIG


def load_config(path: Path | None = None) -> Config:
    """Load the exclusion config; an absent file yields the empty default."""
    path = path or _config_path()
    if not path.exists():
        return Config()
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    excl = raw.get("exclusions", {}) or {}
    regions = tuple(
        Rect(r["x"], r["y"], r["width"], r["height"])
        for r in (excl.get("regions") or [])
    )
    return Config(
        exclusions=ExclusionConfig(
            apps=tuple(excl.get("apps") or ()),
            window_titles=tuple(excl.get("window_titles") or ()),
            regions=regions,
            secret_roles=tuple(excl.get("secret_roles") or _DEFAULT_SECRET_ROLES),
            secret_apps=tuple(excl.get("secret_apps") or ()),
        )
    )


# --- motor config ---------------------------------------------------------
from .motor.types import Level  # noqa: E402  (kept near its use)

_MOTOR_DEFAULT = config_dir() / "motor.yaml"
_MOTOR_EXAMPLE = _REPO_ROOT / "config" / "motor.example.yaml"

_DEFAULT_ENGAGE = "I ENGAGE DAIMON L4 AUTONOMY ON THIS MACHINE"
_DEFAULT_DISENGAGE = "I DISENGAGE DAIMON L4 AUTONOMY"


@dataclass(frozen=True)
class MotorConfig:
    """Motor authorization settings: static ceiling and L4 consent phrases."""

    ceiling: Level = Level.READ
    engagement_phrase: str = _DEFAULT_ENGAGE
    disengagement_phrase: str = _DEFAULT_DISENGAGE


def _motor_path() -> Path:
    """Resolve the motor config path (env > user data > example)."""
    env = os.environ.get("DAIMON_MOTOR_CONFIG")
    if env:
        return Path(env).expanduser()
    if _MOTOR_DEFAULT.exists():
        return _MOTOR_DEFAULT
    return _MOTOR_EXAMPLE


def _parse_static_ceiling(name) -> Level:
    """Parse a config ceiling, clamped to VALIDATION.

    L4/AUTONOMOUS must never come from static config — it requires written human
    engagement recorded in the consent ledger. An unknown name falls back to the
    safe default (READ).
    """
    if not name:
        return Level.READ
    try:
        level = Level[str(name).strip().upper()]
    except KeyError:
        return Level.READ
    return level if level <= Level.VALIDATION else Level.VALIDATION


def load_motor_config(path: Path | None = None) -> MotorConfig:
    """Load the motor config; ceiling is clamped so L4 can't come from a file."""
    path = path or _motor_path()
    if not path.exists():
        return MotorConfig()
    raw = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("motor", {}) or {}
    ceiling = _parse_static_ceiling(raw.get("ceiling"))
    l4 = raw.get("l4", {}) or {}
    return MotorConfig(
        ceiling=ceiling,
        engagement_phrase=l4.get("engagement_phrase", _DEFAULT_ENGAGE),
        disengagement_phrase=l4.get("disengagement_phrase", _DEFAULT_DISENGAGE),
    )


# --- overlay config -------------------------------------------------------
_OVERLAY_DEFAULT = config_dir() / "overlay.yaml"
_OVERLAY_EXAMPLE = _REPO_ROOT / "config" / "overlay.example.yaml"


@dataclass(frozen=True)
class OverlayConfig:
    """HUD overlay settings: whether it runs and how it renders."""

    enabled: bool = False
    opacity: float = 0.95
    anti_feedback: bool = True   # exclude the overlay from screen capture


def _overlay_path() -> Path:
    """Resolve the overlay config path (env > user data > example)."""
    env = os.environ.get("DAIMON_OVERLAY_CONFIG")
    if env:
        return Path(env).expanduser()
    return _OVERLAY_DEFAULT if _OVERLAY_DEFAULT.exists() else _OVERLAY_EXAMPLE


def load_overlay_config(path: Path | None = None) -> OverlayConfig:
    """Load the overlay config; an absent file yields the disabled default."""
    path = path or _overlay_path()
    if not path.exists():
        return OverlayConfig()
    raw = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("overlay", {}) or {}
    return OverlayConfig(
        enabled=bool(raw.get("enabled", False)),
        opacity=float(raw.get("opacity", 0.95)),
        anti_feedback=bool(raw.get("anti_feedback", True)),
    )


# --- update config --------------------------------------------------------
_UPDATE_DEFAULT = config_dir() / "update.yaml"
_UPDATE_EXAMPLE = _REPO_ROOT / "config" / "update.example.yaml"
_DEFAULT_MANIFEST_URL = (
    "https://github.com/ArboRithmDev/Daimon/releases/latest/download/latest.json"
)


@dataclass(frozen=True)
class UpdateConfig:
    enabled: bool = True
    manifest_url: str = _DEFAULT_MANIFEST_URL
    interval_hours: float = 24.0
    auto_apply: bool = False        # notify by default; apply only on click
    allow_prerelease: bool = False


def _update_path() -> Path:
    env = os.environ.get("DAIMON_UPDATE_CONFIG")
    if env:
        return Path(env).expanduser()
    return _UPDATE_DEFAULT if _UPDATE_DEFAULT.exists() else _UPDATE_EXAMPLE


def load_update_config(path: Path | None = None) -> UpdateConfig:
    """Load the auto-update config; an absent file yields the safe defaults
    (enabled, notify-only, stable channel, 24h interval)."""
    path = path or _update_path()
    if not path.exists():
        return UpdateConfig()
    raw = (yaml.safe_load(path.read_text(encoding="utf-8")) or {}).get("update", {}) or {}
    return UpdateConfig(
        enabled=bool(raw.get("enabled", True)),
        manifest_url=str(raw.get("manifest_url") or _DEFAULT_MANIFEST_URL),
        interval_hours=float(raw.get("interval_hours", 24.0)),
        auto_apply=bool(raw.get("auto_apply", False)),
        allow_prerelease=bool(raw.get("allow_prerelease", False)),
    )
