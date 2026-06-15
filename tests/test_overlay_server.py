"""Lifecycle of the overlay socket server: it must terminate when the last
driver disconnects, and never while a driver is still (re)connected — this is
what stops overlay processes from piling up in parallel."""

from __future__ import annotations

from daimon.overlay.app.server import OverlayServer


class _FakeScene:
    def __init__(self):
        self.applied = []

    def apply(self, cmd):
        self.applied.append(cmd)


def _server():
    """Server with controllable scheduler + terminate seams.

    Returns (server, pending, terminated) where `pending` collects scheduled
    quit callbacks (fire manually) and `terminated` records terminate calls.
    """
    pending = []
    terminated = []
    srv = OverlayServer(
        _FakeScene(), flip_height=1000, idle_grace=0,
        scheduler=lambda delay, fn: pending.append(fn),
        terminate=lambda: terminated.append(True),
        main_dispatch=lambda fn, arg: fn(arg),   # apply synchronously
    )
    return srv, pending, terminated


def test_quits_when_last_client_leaves():
    srv, pending, terminated = _server()
    srv._client_added()
    srv._client_removed()
    assert len(pending) == 1, "idle should arm exactly one quit timer"
    pending[0]()
    assert terminated == [True]


def test_does_not_quit_while_a_client_remains():
    srv, pending, terminated = _server()
    srv._client_added()
    srv._client_added()
    srv._client_removed()           # one driver still connected
    # no quit armed while clients remain
    assert pending == []
    assert terminated == []


def test_reconnect_cancels_pending_quit():
    srv, pending, terminated = _server()
    srv._client_added()
    srv._client_removed()           # arms quit
    assert len(pending) == 1
    srv._client_added()             # a driver reconnected → must cancel
    pending[0]()                    # fire the stale timer
    assert terminated == [], "a reconnected client must veto the pending quit"


def test_scene_cleared_on_idle():
    srv, pending, terminated = _server()
    srv._client_added()
    srv._client_removed()
    # Clear is dispatched to the scene when the last client leaves.
    assert any(getattr(c, "cmd", None) == "clear" for c in srv._scene.applied)
