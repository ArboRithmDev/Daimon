"""The frozen-app version fallback must match pyproject.toml.

The .app has no package metadata, so it shows daimon._FALLBACK_VERSION. If that
drifts from pyproject the menu reports a stale version (it once stuck at 0.0.1).
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


def test_fallback_matches_pyproject():
    assert daimon._FALLBACK_VERSION == _pyproject_version()
