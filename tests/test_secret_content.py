# tests/test_secret_content.py
from daimon.config import ExclusionConfig
from daimon.exclusions import ExclusionFilter


def _f(**kw):
    return ExclusionFilter(ExclusionConfig(**kw))


def test_secret_role_node_value_is_blanked():
    f = _f(secret_roles=("AXSecureTextField",))
    tree = {"role": "AXWindow", "title": "W", "children": [
        {"role": "AXSecureTextField", "title": None, "value": "hunter2"},
        {"role": "AXStaticText", "title": None, "value": "ok"},
    ]}
    out = f.redact_nodes([tree])[0]
    secure = out["children"][0]
    assert secure["value"] != "hunter2"
    assert secure.get("redacted") is True
    assert out["children"][1]["value"] == "ok"


def test_is_target_secret_by_role_and_app():
    f = _f(secret_roles=("AXSecureTextField",), secret_apps=("com.x.vault",))
    assert f.is_target_secret(role="AXSecureTextField", bundle_id=None)
    assert f.is_target_secret(role=None, bundle_id="com.x.vault")
    assert not f.is_target_secret(role="AXButton", bundle_id="com.x.safe")


def test_title_excluded_node_still_dropped():
    # existing behaviour preserved
    f = _f(window_titles=(r"(?i)password",))
    tree = {"role": "AXWindow", "title": "Password vault", "children": []}
    assert f.redact_nodes([tree]) == []
