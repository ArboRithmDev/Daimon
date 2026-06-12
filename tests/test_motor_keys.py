import pytest
from daimon.motor.keys import keycode_for, modifier_mask, KEYCODES


def test_known_keys_map_to_codes():
    for name in ["return", "tab", "escape", "left", "a", "f5"]:
        assert isinstance(keycode_for(name), int)


def test_key_lookup_is_case_insensitive():
    assert keycode_for("Return") == keycode_for("return")


def test_unknown_key_raises():
    with pytest.raises(KeyError):
        keycode_for("nope-key")


def test_modifier_mask_combines():
    assert modifier_mask(["cmd", "shift"]) == modifier_mask(["shift", "cmd"])
    assert modifier_mask([]) == 0
    assert modifier_mask(["cmd"]) != 0
