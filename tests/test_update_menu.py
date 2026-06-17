"""Update entries in the pure tray menu + update config loading. Any platform."""

from daimon.motor.types import Level
from daimon.tray.menu_model import UpdateMenuState, build_menu
from daimon.tray.state import TrayState


def _state():
    return TrayState(version="0.0.7", screen_ok=True, accessibility_ok=True,
                     clients=(), ceiling=Level.READ, l4_active=False, overlay_on=False)


def _labels(items):
    out = []
    for it in items:
        out.append(it.label)
    return out


def test_check_for_updates_shown_by_default():
    actions = {i.action_id: i.label for i in build_menu(_state()) if i.action_id}
    assert actions.get("check_update") == "Check for updates"
    assert "apply_update" not in actions


def test_update_available_shows_apply_action():
    items = build_menu(_state(), UpdateMenuState(available_version="0.0.9"))
    apply = next((i for i in items if i.action_id == "apply_update"), None)
    assert apply is not None and "0.0.9" in apply.label
    assert all(i.action_id != "check_update" for i in items)


def test_checking_shows_disabled_label():
    items = build_menu(_state(), UpdateMenuState(checking=True))
    lbl = next((i for i in items if "Checking" in i.label), None)
    assert lbl is not None and lbl.enabled is False


def test_update_config_defaults_and_override(tmp_path, monkeypatch):
    from daimon.config import load_update_config
    cfg = load_update_config(tmp_path / "nope.yaml")     # absent → defaults
    assert cfg.enabled is True and cfg.auto_apply is False
    assert cfg.manifest_url.startswith("https://")
    p = tmp_path / "update.yaml"
    p.write_text("update:\n  enabled: false\n  auto_apply: true\n  interval_hours: 6\n",
                 encoding="utf-8")
    cfg = load_update_config(p)
    assert cfg.enabled is False and cfg.auto_apply is True and cfg.interval_hours == 6.0
