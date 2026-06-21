from daimon.face.view_model import serialize, BRAND
from daimon.tray.state import TrayState, ClientStatus
from daimon.motor.types import Level


def _state(**kw):
    base = dict(version="0.1.0", screen_ok=True, accessibility_ok=False,
                clients=(ClientStatus("Claude", True), ClientStatus("Cursor", False)),
                ceiling=Level.INPUT, l4_active=False, overlay_on=True)
    base.update(kw)
    return TrayState(**base)


def test_serialize_shape_and_values():
    v = serialize(_state())
    assert v["version"] == "0.1.0"
    assert v["permissions"] == {"screen_recording": True, "accessibility": False}
    assert v["clients"] == [{"name": "Claude", "registered": True},
                            {"name": "Cursor", "registered": False}]
    assert v["ceiling"]["current"] == "INPUT"
    assert v["ceiling"]["settable"] == ["READ", "NONDESTRUCTIVE", "INPUT", "VALIDATION"]
    assert v["ceiling"]["l4_active"] is False
    assert v["overlay_on"] is True


def test_serialize_carries_locked_brand_track():
    v = serialize(_state())
    # The locked brand track is carried verbatim, plus a per-OS `backdrop` hint
    # (the web layer paints a solid card off macOS, a translucent one over vibrancy).
    assert {k: v["brand"][k] for k in BRAND} == BRAND
    assert v["brand"]["backdrop"] in ("vibrancy", "solid")
    assert BRAND["presence"] == "#B66CFF" and BRAND["companion"] == "#E8B23A"
    assert BRAND["finish"] == "indigo" and BRAND["lead"] == "beside" and BRAND["style"] == "organic"


def test_serialize_never_exposes_autonomous_as_settable():
    assert "AUTONOMOUS" not in serialize(_state(ceiling=Level.AUTONOMOUS))["ceiling"]["settable"]


def test_serialize_reports_l4_active():
    assert serialize(_state(l4_active=True))["ceiling"]["l4_active"] is True


def test_serialize_is_json_safe():
    import json
    json.dumps(serialize(_state()))  # must not raise (no enums/objects leak)
