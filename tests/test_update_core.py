"""Pure update-decision tests — run on every platform."""

import pytest

from daimon.update import core


def test_parse_version_release_and_prerelease():
    assert core.parse_version("0.0.8") == ((0, 0, 8), ())
    assert core.parse_version("v1.2.3") == ((1, 2, 3), ())
    assert core.parse_version("0.0.8-beta.1") == ((0, 0, 8), ("beta", "1"))


def test_is_newer_basic_ordering():
    assert core.is_newer("0.0.8", "0.0.7") is True
    assert core.is_newer("0.1.0", "0.0.9") is True
    assert core.is_newer("0.0.7", "0.0.7") is False        # equal
    assert core.is_newer("0.0.6", "0.0.7") is False        # older


def test_final_release_outranks_its_prerelease():
    assert core.is_newer("0.0.8", "0.0.8-beta") is True
    assert core.is_newer("0.0.8-beta", "0.0.8") is False


def test_prereleases_skipped_unless_allowed():
    assert core.is_newer("0.0.9-beta", "0.0.8") is False               # not offered
    assert core.is_newer("0.0.9-beta", "0.0.8", allow_prerelease=True) is True


def test_select_asset_present_missing_incomplete():
    man = {"assets": {"win64": {"url": "https://x/y.exe", "sha256": "abc"}}}
    assert core.select_asset(man, "win64")["url"] == "https://x/y.exe"
    assert core.select_asset(man, "macos") is None                     # absent
    assert core.select_asset({"assets": {"win64": {"url": "https://x"}}}, "win64") is None  # no sha


_MANIFEST = {
    "version": "0.0.8",
    "notes": "fixes",
    "assets": {
        "win64": {"url": "https://r/Daimon-0.0.8-setup.exe", "sha256": "W"},
        "macos": {"url": "https://r/Daimon-0.0.8.dmg", "sha256": "M"},
    },
}


def test_decide_returns_info_for_this_platform():
    info = core.decide(_MANIFEST, "0.0.7", key="win64")
    assert info is not None
    assert info.version == "0.0.8" and info.url.endswith("setup.exe") and info.sha256 == "W"
    assert info.notes == "fixes"


def test_decide_none_when_up_to_date_or_no_asset():
    assert core.decide(_MANIFEST, "0.0.8", key="win64") is None        # same version
    assert core.decide(_MANIFEST, "0.0.7", key="linux") is None        # no asset for platform


def test_platform_key_for_current_os():
    import sys
    expected = {"win32": "win64", "darwin": "macos"}.get(sys.platform, sys.platform)
    assert core.platform_key() == expected


def test_source_rejects_non_https():
    from daimon.update import source
    with pytest.raises(ValueError):
        source.fetch_manifest("http://insecure/latest.json")
