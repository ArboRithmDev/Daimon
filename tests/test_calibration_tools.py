"""Calibration MCP tools wiring: vue_calibrate (capture->persist) + auto-match.

Exercised with fake displays and a FakeProfileStore — no real screen, no disk.
DoD: capture->persist->relaunch->auto-match by signature; unknown profile
detected; coord round-trip via a profile.
"""

import pytest

from daimon.capture.screen import Display
from daimon.senses.calibration import profile_from_displays
from daimon.senses.calibration_store import FakeProfileStore


@pytest.fixture(autouse=True)
def _seam_screen(monkeypatch):
    """Route the screen seam at the (patched) macOS screen module so this
    OS-agnostic test runs on Windows too (prod resolves via backends.build_screen,
    which off macOS would return screen_win and bypass the patch)."""
    import daimon.backends as backends
    import daimon.capture.screen as screen
    monkeypatch.setattr(backends, "build_screen", lambda: screen)


_DESK = [
    Display(index=0, display_id=1, width=1920, height=1080, is_main=True,
            origin_x=0, origin_y=0, dpi=96),
    Display(index=1, display_id=2, width=1920, height=1080, is_main=False,
            origin_x=-1920, origin_y=0, dpi=96),
]
_LAPTOP = [
    Display(index=0, display_id=9, width=1512, height=982, is_main=True,
            origin_x=0, origin_y=0, dpi=226),
]


class _FakeExclusions:
    def evaluate_frontmost(self, bundle):
        class _G:
            refused = False
            reason = ""
        return _G()

    def redact_image(self, image):
        return image


class _ToolReg:
    def __init__(self):
        self.tools = {}

    def tool(self, name, description=""):
        def deco(fn):
            self.tools[name] = fn
            return fn
        return deco


def _make_vue(store):
    from daimon.senses.vue import Vue
    return Vue(_FakeExclusions(), profile_store=store)


def _register(monkeypatch, displays, store):
    import daimon.capture.screen as screen
    monkeypatch.setattr(screen, "list_displays", lambda: displays)
    reg = _ToolReg()
    _make_vue(store).register(reg)
    return reg


# --- vue_calibrate: capture topology -> persist -----------------------------


def test_vue_calibrate_persists_named_profile(monkeypatch):
    store = FakeProfileStore()
    reg = _register(monkeypatch, _DESK, store)
    out = reg.tools["vue_calibrate"](name="bureau-3-ecrans")
    assert out["saved"] is True
    assert out["name"] == "bureau-3-ecrans"
    assert out["display_count"] == 2
    # persisted: a relaunch would find it
    assert store.match(_DESK).name == "bureau-3-ecrans"


def test_vue_calibrate_requires_a_name(monkeypatch):
    store = FakeProfileStore()
    reg = _register(monkeypatch, _DESK, store)
    with pytest.raises(ValueError):
        reg.tools["vue_calibrate"](name="")


def test_vue_calibrate_recapture_same_name_upserts(monkeypatch):
    store = FakeProfileStore()
    store.save(profile_from_displays("bureau", _LAPTOP))  # stale layout
    reg = _register(monkeypatch, _DESK, store)
    reg.tools["vue_calibrate"](name="bureau")
    assert len(store.load_all()) == 1
    assert store.match(_DESK).name == "bureau"


# --- vue_profile: report the auto-matched active profile --------------------


def test_vue_profile_auto_matches_known(monkeypatch):
    store = FakeProfileStore()
    store.save(profile_from_displays("bureau-3-ecrans", _DESK))
    reg = _register(monkeypatch, _DESK, store)
    out = reg.tools["vue_profile"]()
    assert out["matched"] is True
    assert out["active_profile"] == "bureau-3-ecrans"
    assert "signature" in out


def test_vue_profile_unknown_signals_and_proposes(monkeypatch):
    store = FakeProfileStore()
    store.save(profile_from_displays("portable-seul", _LAPTOP))
    reg = _register(monkeypatch, _DESK, store)
    out = reg.tools["vue_profile"]()
    assert out["matched"] is False
    assert out["active_profile"] is None
    # proposes creating one (names the calibrate tool)
    assert "vue_calibrate" in out["hint"]
    assert out["known_profiles"] == ["portable-seul"]


# --- coord round-trip via the active profile (AXE 1 fed from profile) -------


def test_vue_profile_resolves_coords_from_profile(monkeypatch):
    store = FakeProfileStore()
    store.save(profile_from_displays("bureau", _DESK))
    reg = _register(monkeypatch, _DESK, store)
    # resolve using the profile's stored geometry, not a re-probe
    out = reg.tools["vue_resolve"](display=1, max_width=1600,
                                   image_x=1600, image_y=0, source="profile")
    assert out == {"global_x": 0, "global_y": 0}


def test_vue_resolve_profile_source_unknown_falls_back(monkeypatch):
    # No saved profile for this env -> source="profile" can't match -> falls
    # back to live probing rather than failing the resolve.
    store = FakeProfileStore()
    reg = _register(monkeypatch, _DESK, store)
    out = reg.tools["vue_resolve"](display=1, max_width=1600,
                                   image_x=1600, image_y=0, source="profile")
    assert out == {"global_x": 0, "global_y": 0}
