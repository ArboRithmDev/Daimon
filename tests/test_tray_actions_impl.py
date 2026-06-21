"""Unit tests for the injected-callback wiring of TrayActions (the L4 gate and
the host delegations). The settings/deploy/consent effects are exercised live."""
from daimon.tray.actions_impl import TrayActions
from daimon.tray.actions import ActionRouter


def test_quit_delegates_to_callback():
    calls = []
    a = TrayActions(on_quit=lambda: calls.append("q"))
    a.quit()
    assert calls == ["q"]


def test_run_setup_opens_onboarding():
    calls = []
    a = TrayActions(open_onboarding=lambda: calls.append("onb"))
    a.run_setup()
    assert calls == ["onb"]


def test_engage_l4_refuses_without_confirmation(monkeypatch):
    # Default confirm_l4 returns False -> consent must never be engaged.
    engaged = []

    class _Consent:
        def engage_confirmed(self, **kw): engaged.append(kw)

    import daimon.motor.factory as factory
    monkeypatch.setattr(factory, "build_consent", lambda: _Consent(), raising=True)
    TrayActions().engage_l4()  # confirm defaults to False
    assert engaged == []


def test_engage_l4_engages_when_confirmed(monkeypatch):
    engaged, changed = [], []

    class _Consent:
        def engage_confirmed(self, **kw): engaged.append(kw)

    import daimon.motor.factory as factory
    monkeypatch.setattr(factory, "build_consent", lambda: _Consent(), raising=True)
    a = TrayActions(confirm_l4=lambda: True, on_change=lambda: changed.append(1))
    a.engage_l4()
    assert len(engaged) == 1 and engaged[0]["source"] == "tray"
    assert changed == [1]


def test_router_over_trayactions_refuses_l4_set():
    # End to end: the router still blocks set_ceiling:AUTONOMOUS over real handlers.
    a = TrayActions()
    assert ActionRouter(a).dispatch("set_ceiling:AUTONOMOUS").ok is False
