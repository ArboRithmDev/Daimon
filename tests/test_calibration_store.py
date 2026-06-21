"""Calibration profile store — persistence in the per-OS data dir.

Follows the config doctrine: atomic writes, timestamped backup before
overwrite, idempotent save, reversible. The store is pure-ish (it only touches
the filesystem under DAIMON_DATA_DIR) so it is exercised here with a tmp_path,
no real screen needed. A FakeProfileStore gives the tool/boot tests an
in-memory twin.
"""

import json

from daimon.capture.screen import Display
from daimon.senses.calibration import (
    environment_signature,
    profile_from_displays,
)
from daimon.senses.calibration_store import (
    FakeProfileStore,
    ProfileStore,
    profiles_path,
)


_DESK = [
    Display(index=0, display_id=1, width=1920, height=1080, is_main=True,
            origin_x=0, origin_y=0, dpi=96),
    Display(index=1, display_id=2, width=1920, height=1080, is_main=False,
            origin_x=-1920, origin_y=0, dpi=96),
]
_LAPTOP = [
    Display(index=0, display_id=9, width=1512, height=982, is_main=True,
            origin_x=0, origin_y=0, dpi=226),
]


def _store(tmp_path, monkeypatch):
    monkeypatch.setenv("DAIMON_DATA_DIR", str(tmp_path))
    return ProfileStore()


# --- path lives in the per-OS data dir --------------------------------------


def test_profiles_path_under_data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DAIMON_DATA_DIR", str(tmp_path))
    p = profiles_path()
    assert p == tmp_path / "config" / "calibration.json"


# --- save then load (relaunch) ----------------------------------------------


def test_save_then_load_round_trip(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    desk = profile_from_displays("bureau", _DESK)
    store.save(desk)

    reloaded = ProfileStore().load_all()  # fresh store = relaunch
    assert len(reloaded) == 1
    assert reloaded[0] == desk


def test_save_writes_valid_json(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    store.save(profile_from_displays("bureau", _DESK))
    raw = json.loads(profiles_path().read_text(encoding="utf-8"))
    assert raw["version"] == 2
    assert raw["profiles"][0]["name"] == "bureau"


def test_load_all_missing_file_is_empty(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    assert store.load_all() == []


# --- idempotent + upsert by name --------------------------------------------


def test_save_same_name_replaces_not_duplicates(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    store.save(profile_from_displays("bureau", _DESK))
    # recapture the same name with a different layout (laptop)
    store.save(profile_from_displays("bureau", _LAPTOP))
    all_ = ProfileStore().load_all()
    assert len(all_) == 1
    assert all_[0].signature == environment_signature(_LAPTOP)


def test_save_distinct_names_accumulate(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    store.save(profile_from_displays("bureau", _DESK))
    store.save(profile_from_displays("portable", _LAPTOP))
    names = {p.name for p in ProfileStore().load_all()}
    assert names == {"bureau", "portable"}


# --- backup before overwrite (reversible) -----------------------------------


def test_overwrite_leaves_a_backup(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    store.save(profile_from_displays("bureau", _DESK))
    store.save(profile_from_displays("portable", _LAPTOP))
    backups = list(profiles_path().parent.glob("calibration.json.bak.*"))
    assert backups, "expected a timestamped backup on overwrite"


def test_no_tmp_file_left_behind(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    store.save(profile_from_displays("bureau", _DESK))
    assert not list(profiles_path().parent.glob("*.tmp"))


# --- match against the persisted store --------------------------------------


def test_active_profile_auto_match(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    store.save(profile_from_displays("bureau", _DESK))
    store.save(profile_from_displays("portable", _LAPTOP))
    matched = ProfileStore().match(_LAPTOP)
    assert matched is not None and matched.name == "portable"


def test_match_unknown_environment_returns_none(tmp_path, monkeypatch):
    store = _store(tmp_path, monkeypatch)
    store.save(profile_from_displays("portable", _LAPTOP))
    assert ProfileStore().match(_DESK) is None


# --- Fake store: in-memory twin for tool/boot tests -------------------------


def test_fake_store_save_and_match():
    fake = FakeProfileStore()
    fake.save(profile_from_displays("bureau", _DESK))
    assert fake.match(_DESK).name == "bureau"
    assert fake.match(_LAPTOP) is None


def test_fake_store_upsert_by_name():
    fake = FakeProfileStore()
    fake.save(profile_from_displays("bureau", _DESK))
    fake.save(profile_from_displays("bureau", _LAPTOP))
    assert len(fake.load_all()) == 1
    assert fake.match(_LAPTOP).name == "bureau"
