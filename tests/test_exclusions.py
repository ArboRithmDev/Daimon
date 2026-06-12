"""Exclusion filter is the security-critical layer — test it without macOS deps."""

from daimon.config import ExclusionConfig, Rect
from daimon.exclusions import ExclusionFilter


def _filter(**kw) -> ExclusionFilter:
    return ExclusionFilter(ExclusionConfig(**kw))


def test_frontmost_excluded_app_refuses_snapshot():
    f = _filter(apps=("com.1password.1password",))
    result = f.evaluate_frontmost("com.1password.1password")
    assert result.refused
    assert "1password" in result.reason


def test_frontmost_allowed_app_passes():
    f = _filter(apps=("com.1password.1password",))
    assert not f.evaluate_frontmost("com.apple.Safari").refused


def test_frontmost_none_passes():
    assert not _filter(apps=("x",)).evaluate_frontmost(None).refused


def test_title_regex_match():
    f = _filter(window_titles=(r"(?i)password",))
    assert f.is_title_excluded("My PASSWORD vault")
    assert not f.is_title_excluded("untitled document")


def test_regions_exposed():
    r = Rect(0, 0, 100, 50)
    assert _filter(regions=(r,)).regions == (r,)


def test_empty_filter_excludes_nothing():
    f = _filter()
    assert not f.is_app_excluded("com.anything")
    assert not f.is_title_excluded("anything")
    assert f.regions == ()
