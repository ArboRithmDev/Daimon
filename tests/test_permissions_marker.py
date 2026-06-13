from daimon.setup.permissions import FakeBackend, read_status, record_status, status_marker_path


def test_record_then_read_round_trip(tmp_path):
    p = tmp_path / "permissions.json"
    data = record_status(FakeBackend(screen=True, accessibility=False), path=p)
    assert data == {"screen_recording": True, "accessibility": False}
    assert read_status(p) == data


def test_read_missing_is_empty(tmp_path):
    assert read_status(tmp_path / "nope.json") == {}


def test_record_creates_parent_dirs(tmp_path):
    p = tmp_path / "a" / "b" / "permissions.json"
    record_status(FakeBackend(screen=True, accessibility=True), path=p)
    assert p.exists()


def test_marker_path_under_application_support():
    assert str(status_marker_path()).endswith("Library/Application Support/Daimon/permissions.json")
