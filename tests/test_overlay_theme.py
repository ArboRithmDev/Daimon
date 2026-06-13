# tests/test_overlay_theme.py
from daimon.overlay.theme import style_for, STYLES


def test_known_styles_have_color_and_duration():
    for style in ["default", "L1", "L2", "L3", "gate"]:
        s = style_for(style)
        assert "rgba" in s and "duration" in s and "radius" in s
        assert len(s["rgba"]) == 4


def test_gate_is_red_and_pulses():
    s = style_for("gate")
    r, g, b, a = s["rgba"]
    assert r > 0.7 and g < 0.4 and b < 0.4  # red
    assert s["pulse"] is True


def test_unknown_style_falls_back_to_default():
    assert style_for("???") == STYLES["default"]
