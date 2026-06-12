from daimon.config import load_motor_config
from daimon.motor.types import Level


def test_defaults_to_l0_and_has_phrases(tmp_path):
    cfg = load_motor_config(tmp_path / "missing.yaml")
    assert cfg.ceiling == Level.READ
    assert cfg.engagement_phrase
    assert cfg.disengagement_phrase


def test_loads_ceiling_and_phrases(tmp_path):
    p = tmp_path / "motor.yaml"
    p.write_text(
        "motor:\n"
        "  ceiling: INPUT\n"
        "  l4:\n"
        "    engagement_phrase: GO\n"
        "    disengagement_phrase: STOP\n",
        encoding="utf-8",
    )
    cfg = load_motor_config(p)
    assert cfg.ceiling == Level.INPUT
    assert cfg.engagement_phrase == "GO"
    assert cfg.disengagement_phrase == "STOP"


def test_ceiling_autonomous_in_config_is_clamped_to_validation(tmp_path):
    # L4 must never come from static config — only from written human engagement.
    p = tmp_path / "motor.yaml"
    p.write_text("motor:\n  ceiling: AUTONOMOUS\n", encoding="utf-8")
    cfg = load_motor_config(p)
    assert cfg.ceiling == Level.VALIDATION


def test_invalid_ceiling_name_falls_back_to_read(tmp_path):
    p = tmp_path / "motor.yaml"
    p.write_text("motor:\n  ceiling: BOGUS\n", encoding="utf-8")
    cfg = load_motor_config(p)
    assert cfg.ceiling == Level.READ
