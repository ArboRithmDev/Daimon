"""Release manifest generation/merge. Imports the build helper directly."""

import importlib.util
import json
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "make_manifest", Path(__file__).resolve().parents[1] / "build" / "make_manifest.py")
mm = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mm)


def _asset(tmp_path, name, content=b"bytes"):
    p = tmp_path / name
    p.write_bytes(content)
    return p


def test_creates_manifest_with_asset_and_sha(tmp_path):
    out = tmp_path / "dist"
    out.mkdir()
    asset = _asset(out, "Daimon-0.0.8-setup.exe", b"win-installer")
    data = mm.update_manifest(out, "0.0.8", "win64", asset, base_url="https://r/dl")
    assert data["version"] == "0.0.8"
    assert data["assets"]["win64"]["url"] == "https://r/dl/Daimon-0.0.8-setup.exe"
    assert data["assets"]["win64"]["sha256"] == mm.sha256(asset)
    # SHA256SUMS written
    sums = (out / "SHA256SUMS").read_text(encoding="utf-8")
    assert "Daimon-0.0.8-setup.exe" in sums


def test_merges_two_platforms_into_one_manifest(tmp_path):
    out = tmp_path / "dist"
    out.mkdir()
    win = _asset(out, "Daimon-0.0.8-setup.exe", b"win")
    mac = _asset(out, "Daimon-0.0.8.dmg", b"mac")
    mm.update_manifest(out, "0.0.8", "win64", win)
    mm.update_manifest(out, "0.0.8", "macos", mac)
    data = json.loads((out / "latest.json").read_text(encoding="utf-8"))
    assert set(data["assets"]) == {"win64", "macos"}


def test_version_bump_resets_assets(tmp_path):
    out = tmp_path / "dist"
    out.mkdir()
    mm.update_manifest(out, "0.0.8", "win64", _asset(out, "a.exe"))
    mm.update_manifest(out, "0.0.9", "macos", _asset(out, "b.dmg"))
    data = json.loads((out / "latest.json").read_text(encoding="utf-8"))
    assert data["version"] == "0.0.9"
    assert set(data["assets"]) == {"macos"}   # old win64 dropped on bump
