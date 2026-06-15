"""Pure tests for the Windows VK key table — run on every platform."""

from daimon.motor import keys as mac_keys
from daimon.motor import keys_win


def test_covers_the_same_key_vocabulary_as_macos():
    # Every key name the macOS table knows must exist on Windows too, so the
    # same agent vocabulary works on both OSes.
    assert set(mac_keys.KEYCODES) <= set(keys_win.VK)


def test_known_vk_values():
    assert keys_win.vk_for("return") == 0x0D
    assert keys_win.vk_for("a") == 0x41
    assert keys_win.vk_for("z") == 0x5A
    assert keys_win.vk_for("0") == 0x30
    assert keys_win.vk_for("9") == 0x39
    assert keys_win.vk_for("f1") == 0x70
    assert keys_win.vk_for("left") == 0x25


def test_vk_for_is_case_insensitive():
    assert keys_win.vk_for("ESC") == keys_win.vk_for("esc") == 0x1B


def test_modifier_vks_resolve_to_hold_keys():
    assert keys_win.modifier_vks(["ctrl", "shift"]) == [0x11, 0x10]
    assert keys_win.modifier_vks(["alt"]) == [0x12]
    assert keys_win.modifier_vks([]) == []


def test_macos_modifier_names_are_all_mapped():
    for name in mac_keys._MOD_FLAGS:
        assert keys_win.modifier_vks([name])  # no KeyError, non-empty
