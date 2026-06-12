from daimon.motor.watchdog import HoldWatchdog


def test_release_after_timeout():
    released = []
    now = [0.0]
    wd = HoldWatchdog(timeout=5.0, release=lambda h: released.append(h), clock=lambda: now[0])
    wd.hold("mouse_left")
    now[0] = 6.0
    wd.tick()
    assert released == ["mouse_left"]


def test_explicit_release_cancels_watchdog():
    released = []
    now = [0.0]
    wd = HoldWatchdog(timeout=5.0, release=lambda h: released.append(h), clock=lambda: now[0])
    wd.hold("key_shift")
    wd.release_hold("key_shift")
    now[0] = 99.0
    wd.tick()
    assert released == []  # already released explicitly, watchdog must not double-release


def test_not_yet_expired_keeps_hold():
    wd = HoldWatchdog(timeout=5.0, release=lambda h: None, clock=lambda: 1.0)
    wd.hold("mouse_left")
    wd.tick()
    assert "mouse_left" in wd.active()
