from daimon.motor.actions import ACTIONS, level_for
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
        "main_mouse_down", "main_mouse_up", "main_key_down", "main_key_up",
    }


def test_unknown_verb_raises():
    import pytest
    with pytest.raises(KeyError):
        level_for("main_launch_missiles")
