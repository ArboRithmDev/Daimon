from daimon.tray.menu_model import MenuItem, build_menu
from daimon.tray.state import ClientStatus, TrayState
from daimon.motor.types import Level


def _state(**kw):
    base = dict(version="1.0.0", screen_ok=True, accessibility_ok=True,
                clients=(ClientStatus("Claude Code", True),),
                ceiling=Level.INPUT, l4_active=False, overlay_on=False)
    base.update(kw)
    return TrayState(**base)


def _ids(items):
    out = []
    for it in items:
        out.append(it.action_id or it.kind)
        out.extend(_ids(it.children))
    return out


def test_menu_has_status_settings_and_actions():
    items = build_menu(_state())
    ids = _ids(items)
    assert "run_setup" in ids and "quit" in ids and "toggle_overlay" in ids
    assert "set_ceiling:READ" in ids and "set_ceiling:VALIDATION" in ids


def test_ceiling_submenu_marks_current_and_excludes_l4():
    items = build_menu(_state(ceiling=Level.INPUT))
    ceiling = next(i for i in items if i.kind == "submenu" and "lafond" in i.label or "eiling" in i.label.lower())
    radios = {i.action_id: i for i in ceiling.children if i.kind == "radio"}
    assert "set_ceiling:AUTONOMOUS" not in radios          # L4 never settable from the menu
    assert radios["set_ceiling:INPUT"].checked is True       # current marked
    assert radios["set_ceiling:READ"].checked is False


def test_overlay_checkbox_reflects_state():
    on = next(i for i in build_menu(_state(overlay_on=True)) if i.action_id == "toggle_overlay")
    off = next(i for i in build_menu(_state(overlay_on=False)) if i.action_id == "toggle_overlay")
    assert on.checked is True and off.checked is False


def test_permission_labels_show_status():
    items = build_menu(_state(screen_ok=False, accessibility_ok=True))
    labels = [i.label for i in items if i.kind == "label"]
    assert any("Screen Recording" in l and ("⚪" in l or "missing" in l.lower() or "❌" in l) for l in labels)
