import asyncio
from daimon.server import build_server


def test_server_exposes_full_toolset():
    names = {t.name for t in asyncio.run(build_server().list_tools())}
    expected = {
        "vue_displays", "vue_snapshot", "vue_resolve", "vue_find",
        "touche_tree", "touche_probe",
        "main_click", "main_type", "main_press", "main_navigate",
        "main_key", "main_hover", "main_activate", "main_drag",
        "main_mouse_down", "main_mouse_up", "main_key_down", "main_key_up",
    }
    assert expected <= names


def test_server_advertises_delegation_in_instructions():
    instr = getattr(build_server(), "instructions", "") or ""
    assert "vue_pilot_brief" in instr


def test_vue_pilot_brief_is_registered():
    import asyncio
    names = {t.name for t in asyncio.run(build_server().list_tools())}
    assert "vue_pilot_brief" in names
