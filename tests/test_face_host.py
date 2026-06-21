from daimon.face.host import FaceHost


class _FakeWindow:
    def __init__(self):
        self.evaluated = []

    def evaluate_js(self, js):
        self.evaluated.append(js)


class _FakeWebview:
    def __init__(self):
        self.created = []

    def create_window(self, title, url, js_api=None, frameless=False, **kw):
        w = _FakeWindow()
        self.created.append({"title": title, "url": url, "js_api": js_api,
                             "frameless": frameless, "kw": kw, "window": w})
        return w


class _FakeBridge:
    def get_state(self):
        return {"version": "0.1.0", "ceiling": {"current": "READ"}}

    def invoke(self, action_id, args=None):
        return {"ok": True, "reason": ""}


def test_open_panel_creates_frameless_window_with_bridge():
    fw = _FakeWebview()
    host = FaceHost(_FakeBridge(), webview_module=fw)
    host.open_panel()
    w = fw.created[-1]
    assert w["frameless"] is True
    assert isinstance(w["js_api"], _FakeBridge)
    assert w["url"].endswith("panel/index.html")
    assert w["url"].startswith("file://")


def test_open_overlay_requests_transparent_on_top():
    fw = _FakeWebview()
    FaceHost(_FakeBridge(), webview_module=fw).open_overlay()
    w = fw.created[-1]
    assert w["frameless"] is True
    assert w["kw"].get("transparent") is True
    assert w["kw"].get("on_top") is True


def test_open_onboarding_is_a_normal_window():
    fw = _FakeWebview()
    FaceHost(_FakeBridge(), webview_module=fw).open_onboarding()
    w = fw.created[-1]
    assert w["url"].endswith("onboarding/index.html")


def test_push_state_dispatches_state_event_to_open_windows():
    fw = _FakeWebview()
    host = FaceHost(_FakeBridge(), webview_module=fw)
    host.open_panel()
    host.push_state()
    evaluated = fw.created[-1]["window"].evaluated
    assert any("daimon:state" in js for js in evaluated)
    assert any("0.1.0" in js for js in evaluated)  # serialized state rode along


def test_push_state_is_noop_when_no_window_open():
    host = FaceHost(_FakeBridge(), webview_module=_FakeWebview())
    host.push_state()  # must not raise


def test_dist_dir_resolves_frozen_meipass(monkeypatch, tmp_path):
    from daimon.face import host
    monkeypatch.setattr(host.sys, "_MEIPASS", str(tmp_path), raising=False)
    d = host._dist_dir()
    assert d == tmp_path / "daimon" / "face" / "web" / "dist"


def test_dist_dir_resolves_source_when_not_frozen(monkeypatch):
    from daimon.face import host
    monkeypatch.delattr(host.sys, "_MEIPASS", raising=False)
    d = host._dist_dir()
    assert d.name == "dist" and d.parent.name == "web"
