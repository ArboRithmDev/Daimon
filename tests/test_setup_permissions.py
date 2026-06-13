from daimon.setup.permissions import FakeBackend, permissions_status, PANE_ACCESSIBILITY


def test_status_reflects_backend():
    b = FakeBackend(screen=True, accessibility=False)
    perms = {p.key: p for p in permissions_status(b)}
    assert perms["screen_recording"].granted is True
    assert perms["accessibility"].granted is False
    assert "Accessibility" in perms["accessibility"].label


def test_open_pane_and_request_recorded():
    b = FakeBackend(screen=False, accessibility=False)
    b.request_accessibility()
    b.open_pane(PANE_ACCESSIBILITY)
    assert b.requested == ["accessibility"]
    assert b.opened == [PANE_ACCESSIBILITY]


def test_all_granted_helper():
    assert all(p.granted for p in permissions_status(FakeBackend(screen=True, accessibility=True)))
