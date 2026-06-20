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


def test_clients_are_toggleable_checkboxes():
    items = build_menu(_state(clients=(
        ClientStatus("Claude Code", True), ClientStatus("Cursor", False))))
    # find the Clients submenu and inspect its rows
    sub = next(i for i in items if i.kind == "submenu" and "Clients" in i.label)
    by_action = {c.action_id: c for c in sub.children if c.kind == "checkbox"}
    assert by_action["toggle_client:Claude Code"].checked is True
    assert by_action["toggle_client:Cursor"].checked is False


def test_install_all_offered_only_when_some_unregistered():
    # one unregistered → install_all present
    items = build_menu(_state(clients=(ClientStatus("Cursor", False),)))
    assert "install_all" in _ids(items)
    # all registered → no install_all
    items = build_menu(_state(clients=(ClientStatus("Claude Code", True),)))
    assert "install_all" not in _ids(items)


def test_no_clients_shows_placeholder():
    items = build_menu(_state(clients=()))
    sub = next(i for i in items if i.kind == "submenu" and "Clients" in i.label)
    assert any("No AI clients detected" in c.label for c in sub.children)


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


def _action_ids(items):
    """Flatten all action_ids from items and their children."""
    out = []
    for it in items:
        out.append(it.action_id)
        out.extend(_action_ids(it.children))
    return out


def test_menu_offers_engage_l4_when_inactive():
    items = build_menu(_state(l4_active=False))
    ids = _action_ids(items)
    assert "engage_l4" in ids and "disengage_l4" not in ids


def test_menu_offers_disengage_l4_when_active():
    items = build_menu(_state(l4_active=True))
    ids = _action_ids(items)
    assert "disengage_l4" in ids and "engage_l4" not in ids


def test_ceiling_radios_stay_l0_to_l3():
    ids = _action_ids(build_menu(_state(l4_active=False)))
    assert "set_ceiling:AUTONOMOUS" not in ids
    assert "set_ceiling:VALIDATION" in ids
