from daimon.tray.actions import ActionRouter, ActionResult


class _Rec:
    def __init__(self):
        self.calls = []

    def set_ceiling(self, name):
        self.calls.append(("set_ceiling", name))

    def toggle_overlay(self):
        self.calls.append(("toggle_overlay",))

    def install_all(self):
        self.calls.append(("install_all",))

    def toggle_client(self, name):
        self.calls.append(("toggle_client", name))

    def engage_l4(self):
        self.calls.append(("engage_l4",))

    def disengage_l4(self):
        self.calls.append(("disengage_l4",))

    def run_setup(self):
        self.calls.append(("run_setup",))

    def open_config(self):
        self.calls.append(("open_config",))

    def open_logs(self):
        self.calls.append(("open_logs",))

    def quit(self):
        self.calls.append(("quit",))


def test_router_dispatches_parameterized_actions():
    rec = _Rec()
    r = ActionRouter(rec)
    assert r.dispatch("set_ceiling:INPUT") == ActionResult(True, "")
    assert r.dispatch("toggle_client:Claude") == ActionResult(True, "")
    assert ("set_ceiling", "INPUT") in rec.calls
    assert ("toggle_client", "Claude") in rec.calls


def test_router_dispatches_simple_actions():
    rec = _Rec()
    r = ActionRouter(rec)
    for aid, expect in [("toggle_overlay", "toggle_overlay"), ("install_all", "install_all"),
                        ("engage_l4", "engage_l4"), ("disengage_l4", "disengage_l4"),
                        ("run_setup", "run_setup"), ("open_config", "open_config"),
                        ("open_logs", "open_logs"), ("quit", "quit")]:
        assert r.dispatch(aid).ok
        assert (expect,) in rec.calls


def test_router_rejects_unknown_action():
    res = ActionRouter(_Rec()).dispatch("rm_-rf")
    assert res.ok is False and "unknown" in res.reason.lower()


def test_router_never_sets_ceiling_to_l4():
    # L4 is consent-gated; set_ceiling:AUTONOMOUS must be refused, not routed.
    rec = _Rec()
    res = ActionRouter(rec).dispatch("set_ceiling:AUTONOMOUS")
    assert res.ok is False and "l4" in res.reason.lower()
    assert rec.calls == []


def test_router_rejects_unknown_ceiling():
    rec = _Rec()
    res = ActionRouter(rec).dispatch("set_ceiling:GODMODE")
    assert res.ok is False and rec.calls == []
