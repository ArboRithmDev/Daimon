"""Version is single-sourced from pyproject.toml's [project].version.

Nothing in the package hardcodes a version literal. __version__ must resolve to
the pyproject value (the menu once stuck at a stale 0.0.1 / 0.0.7 because a
hardcoded fallback drifted — this test makes that impossible).
"""

from __future__ import annotations

import re
from pathlib import Path

import daimon


def _pyproject_version() -> str:
    txt = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'(?m)^version\s*=\s*"([^"]+)"', txt)
    assert m, "version not found in pyproject.toml"
    return m.group(1)


def test_version_is_single_sourced_from_pyproject():
    """In a checkout/editable install, __version__ equals the pyproject value."""
    assert daimon.__version__ == _pyproject_version()


def test_pyproject_reader_matches_pyproject():
    """The source-tree fallback reads the same value (covers the un-installed path)."""
    assert daimon._version_from_pyproject() == _pyproject_version()


def test_no_hardcoded_version_literal_in_init():
    """__init__.py carries no x.y.z version literal — only the resolver."""
    src = Path(daimon.__file__).read_text(encoding="utf-8")
    leftover = [m.group(0) for m in re.finditer(r'"\d+\.\d+\.\d+"', src)]
    assert leftover == [], f"hardcoded version literal(s) found in __init__.py: {leftover}"


def test_stamped_version_used_when_pyproject_absent(monkeypatch):
    """Frozen-app path: with no source pyproject, the build-stamped _version wins."""
    import sys
    import types

    monkeypatch.setattr(daimon, "_version_from_pyproject", lambda: None)
    fake = types.ModuleType("daimon._version")
    fake.__version__ = "9.9.9"
    monkeypatch.setitem(sys.modules, "daimon._version", fake)
    assert daimon._resolve_version() == "9.9.9"
