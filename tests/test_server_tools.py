import asyncio
from daimon.server import build_server


def test_server_exposes_full_toolset():
    names = {t.name for t in asyncio.run(build_server().list_tools())}
    expected = {
        "vue_displays", "vue_snapshot", "touche_tree", "touche_probe",
        "main_click", "main_type", "main_press", "main_navigate",
        "main_key", "main_hover", "main_activate", "main_drag",
        "main_mouse_down", "main_mouse_up", "main_key_down", "main_key_up",
    }
    assert expected <= names
