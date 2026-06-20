"""Daimon — a local sensory organ for AI clients on macOS.

Daimon is an *organ*, not a driver. It never calls an AI and never owns a
perception loop. It exposes senses (Vue, Touché) over MCP; the AI client
pulls perception whenever it wants. Agnostic by construction: any MCP-capable
client (Claude, or any other) plugs in with no per-AI adapter.

Senses are read-only by contract. Daimon reports; it never clicks or types.
The motor organ ("the hands") is out of scope and lives elsewhere.
"""

# Single source of truth for the version is pyproject.toml's [project].version.
# Nothing is hardcoded here — `tests/test_version.py` proves __version__ resolves
# to that one value, so a bump touches pyproject.toml alone. Resolution order is
# "closest authoritative copy of the pyproject value":
#   1. pyproject.toml in the source tree — authoritative in a checkout, and beats
#      a stale editable-install metadata that didn't regenerate on a bump.
#   2. daimon/_version.py — stamped by the build from the pyproject version
#      (the frozen .app has no pyproject in the bundle, so the build freezes the
#      value into the artifact at generation; this file is gitignored).
#   3. installed package metadata (pip wheel install — pip wrote it from pyproject).
#   4. a last-resort sentinel, only if all of the above are unavailable.
# Every path ultimately traces back to the one pyproject.toml value.
from __future__ import annotations

from pathlib import Path

_UNKNOWN = "0.0.0+unknown"


def _version_from_pyproject() -> str | None:
    """Read [project].version from pyproject.toml in the source tree, or None."""
    try:
        import tomllib  # stdlib ≥ 3.11
        pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        return data.get("project", {}).get("version") or None
    except Exception:
        return None


def _resolve_version() -> str:
    # 1. Source-tree pyproject.toml — authoritative in a checkout (beats stale
    #    editable metadata).
    from_pyproject = _version_from_pyproject()
    if from_pyproject:
        return from_pyproject
    # 2. Build-stamped module (frozen app).
    try:
        from ._version import __version__ as _stamped
        if _stamped:
            return _stamped
    except Exception:
        pass
    # 3. Installed package metadata (wheel install).
    try:
        from importlib.metadata import PackageNotFoundError
        from importlib.metadata import version as _pkg_version
        try:
            return _pkg_version("daimon")
        except PackageNotFoundError:
            pass
    except Exception:
        pass
    # 4. Last resort.
    return _UNKNOWN


__version__ = _resolve_version()
