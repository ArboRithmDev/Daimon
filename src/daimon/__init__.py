"""Daimon — a local sensory organ for AI clients on macOS.

Daimon is an *organ*, not a driver. It never calls an AI and never owns a
perception loop. It exposes senses (Vue, Touché) over MCP; the AI client
pulls perception whenever it wants. Agnostic by construction: any MCP-capable
client (Claude, or any other) plugs in with no per-AI adapter.

Senses are read-only by contract. Daimon reports; it never clicks or types.
The motor organ ("the hands") is out of scope and lives elsewhere.
"""

# Single source of truth is pyproject.toml. When Daimon is installed (source or
# `pip install -e .`) we read the real version from the package metadata; the
# frozen .app has no dist metadata, so it falls back to the literal below.
# `tests/test_version.py` asserts this fallback matches pyproject, so the two
# can never silently drift again (the menu used to show a stale 0.0.1).
_FALLBACK_VERSION = "0.0.5"

try:
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as _pkg_version

    try:
        __version__ = _pkg_version("daimon")
    except PackageNotFoundError:
        __version__ = _FALLBACK_VERSION
except Exception:  # pragma: no cover - importlib always present on 3.12
    __version__ = _FALLBACK_VERSION
