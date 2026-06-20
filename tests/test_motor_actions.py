from daimon.motor.actions import ACTIONS, level_for, requires_observed_target, ceiling_report
from daimon.motor.types import Level


def test_registry_maps_verbs_to_levels():
    assert level_for("main_navigate") == Level.NONDESTRUCTIVE
    assert level_for("main_click") == Level.INPUT
    assert level_for("main_type") == Level.INPUT
    assert level_for("main_drag") == Level.INPUT
    assert level_for("main_press") == Level.VALIDATION


def test_registry_is_complete():
    assert set(ACTIONS) == {
        "main_navigate", "main_click", "main_type", "main_drag", "main_press",
        "main_key", "main_hover", "main_activate",
        "main_window_minimize", "main_window_hide", "main_window_show",
        "main_mouse_down", "main_mouse_up", "main_key_down", "main_key_up",
    }


def test_primitives_are_autonomous():
    """actions.py is the single source of truth for primitive levels (N1)."""
    assert level_for("main_mouse_down") == Level.AUTONOMOUS
    assert level_for("main_mouse_up") == Level.AUTONOMOUS
    assert level_for("main_key_down") == Level.AUTONOMOUS
    assert level_for("main_key_up") == Level.AUTONOMOUS


def test_unknown_verb_raises():
    import pytest
    with pytest.raises(KeyError):
        level_for("main_launch_missiles")


def test_requires_observed_target_positional_vs_not():
    for verb in ("click", "press", "drag", "mouse_down", "mouse_up"):
        assert requires_observed_target(verb) is True
    for verb in ("key", "type", "key_down", "key_up", "activate", "hover", "navigate"):
        assert requires_observed_target(verb) is False
    assert requires_observed_target("unknown_verb") is True  # safe default


def test_ceiling_report_at_validation():
    from daimon.motor.actions import ceiling_report
    r = ceiling_report(Level.VALIDATION)
    assert r["ceiling"] == "VALIDATION"
    assert r["l4_active"] is False
    assert r["levels"]["main_click"] == "INPUT"
    # AUTONOMOUS-level primitives are above L3 → gated.
    assert "main_mouse_down" in r["gated_above"]
    # An INPUT-level act is within L3 → not gated.
    assert "main_click" not in r["gated_above"]


def test_ceiling_report_l4_active():
    from daimon.motor.actions import ceiling_report
    assert ceiling_report(Level.AUTONOMOUS)["l4_active"] is True
    assert ceiling_report(Level.AUTONOMOUS)["gated_above"] == []


def test_window_ops_are_nondestructive_and_targetless():
    for tool in ("main_window_minimize", "main_window_hide", "main_window_show"):
        assert tool in ACTIONS
        assert level_for(tool) == Level.NONDESTRUCTIVE
    # SHORT verb form is what the guard/actuator see; observation not required.
    for verb in ("window_minimize", "window_hide", "window_show"):
        assert requires_observed_target(verb) is False
    # exposed in the ceiling report's level map
    assert ceiling_report(Level.VALIDATION)["levels"]["main_window_hide"] == "NONDESTRUCTIVE"
