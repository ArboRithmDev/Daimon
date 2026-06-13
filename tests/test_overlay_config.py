from daimon.config import load_overlay_config


def test_overlay_defaults(tmp_path):
    cfg = load_overlay_config(tmp_path / "missing.yaml")
    assert cfg.enabled in (True, False)
    assert 0.0 < cfg.opacity <= 1.0
    assert cfg.anti_feedback is True


def test_overlay_loads(tmp_path):
    p = tmp_path / "overlay.yaml"
    p.write_text("overlay:\n  enabled: true\n  opacity: 0.8\n  anti_feedback: false\n", encoding="utf-8")
    cfg = load_overlay_config(p)
    assert cfg.enabled is True and cfg.opacity == 0.8 and cfg.anti_feedback is False
