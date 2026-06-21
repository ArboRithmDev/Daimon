from daimon.face.platform import get_adapter


def test_selector_returns_adapter_with_the_contract():
    a = get_adapter()
    for name in ("apply_vibrancy", "exclude_from_capture", "anchor_under_statusitem"):
        assert callable(getattr(a, name))
