from daimon.face.bridge import FaceBridge
from daimon.tray.actions import ActionRouter
from daimon.tray.state import TrayState, ClientStatus
from daimon.motor.types import Level


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


def _state():
    return TrayState(version="0.1.0", screen_ok=True, accessibility_ok=True,
                     clients=(ClientStatus("Claude", True),), ceiling=Level.READ,
                     l4_active=False, overlay_on=False)


def _bridge(rec=None):
    rec = rec or _Rec()
    return FaceBridge(ActionRouter(rec), _state), rec


def test_get_state_returns_serialized_view():
    b, _ = _bridge()
    v = b.get_state()
    assert v["ceiling"]["current"] == "READ"
    assert v["brand"]["presence"] == "#B66CFF"


def test_invoke_routes_and_reports_ok():
    b, rec = _bridge()
    assert b.invoke("toggle_overlay") == {"ok": True, "reason": ""}
    assert ("toggle_overlay",) in rec.calls


def test_invoke_accepts_optional_args():
    b, rec = _bridge()
    assert b.invoke("toggle_client:Cursor", {"unused": 1})["ok"] is True
    assert ("toggle_client", "Cursor") in rec.calls


def test_invoke_rejects_unknown_and_l4_set():
    b, rec = _bridge()
    assert b.invoke("danger")["ok"] is False
    r = b.invoke("set_ceiling:AUTONOMOUS")
    assert r["ok"] is False and "l4" in r["reason"].lower()
    assert rec.calls == []


def test_resize_to_calls_injected_resizer():
    b, _ = _bridge()
    sizes = []
    b.set_resizer(lambda w, h: sizes.append((w, h)))
    assert b.resize_to("340", "700") == {"ok": True}
    assert sizes == [(340, 700)]


def test_resize_to_noop_without_resizer():
    b, _ = _bridge()
    assert b.resize_to(340, 700) == {"ok": True}  # must not raise


def test_close_window_calls_injected_closer():
    b, _ = _bridge()
    closed = []
    b.set_closer(lambda: closed.append(1))
    assert b.close_window() == {"ok": True}
    assert closed == [1]
