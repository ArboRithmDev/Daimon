from daimon.config import load_motor_config, load_overlay_config
from daimon.motor.types import Level
from daimon.tray.settings import set_ceiling, set_overlay


def test_set_ceiling_writes_and_preserves_l4_phrases(tmp_path):
    p = tmp_path / "motor.yaml"
    p.write_text("motor:\n  ceiling: READ\n  l4:\n    engagement_phrase: GO\n", encoding="utf-8")
    set_ceiling("INPUT", path=p)
    cfg = load_motor_config(p)
    assert cfg.ceiling == Level.INPUT
    assert cfg.engagement_phrase == "GO"   # preserved


def test_set_ceiling_clamps_l4(tmp_path):
    p = tmp_path / "motor.yaml"
    set_ceiling("AUTONOMOUS", path=p)
    assert load_motor_config(p).ceiling == Level.VALIDATION   # clamped, never L4


def test_set_overlay_writes(tmp_path):
    p = tmp_path / "overlay.yaml"
    set_overlay(True, path=p)
    assert load_overlay_config(p).enabled is True
    set_overlay(False, path=p)
    assert load_overlay_config(p).enabled is False


def test_set_ceiling_backs_up_existing(tmp_path):
    p = tmp_path / "motor.yaml"
    p.write_text("motor:\n  ceiling: READ\n", encoding="utf-8")
    set_ceiling("INPUT", path=p)
    assert any(x.name.startswith("motor.yaml.bak") for x in tmp_path.iterdir())
