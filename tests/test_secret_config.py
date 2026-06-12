from daimon.config import load_config


def test_secret_roles_and_apps_have_defaults(tmp_path):
    cfg = load_config(tmp_path / "missing.yaml")
    assert "AXSecureTextField" in cfg.exclusions.secret_roles
    assert cfg.exclusions.secret_apps == ()


def test_secret_roles_loaded_from_yaml(tmp_path):
    p = tmp_path / "exclusions.yaml"
    p.write_text(
        "exclusions:\n  secret_roles: [AXSecureTextField, AXMine]\n"
        "  secret_apps: [com.example.vault]\n", encoding="utf-8")
    cfg = load_config(p)
    assert "AXMine" in cfg.exclusions.secret_roles
    assert "com.example.vault" in cfg.exclusions.secret_apps
