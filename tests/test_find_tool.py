"""vue_find MCP tool: Vue-only fallback locator, end-to-end with FakeOCR.

No real screen, no OCR engine. A fake capture yields a Frame whose coord-space is
known; a FakeOCR yields the label's box; vue_find must return GLOBAL coords that,
fed straight to main_click (space='global', the default), land on the label.

This is the DoD round-trip: find("Etat_FACTURECLIENT") -> coords -> click hits it.
"""

import pytest

from daimon.capture.screen import Display, Frame
from daimon.senses.find import WordBox
from daimon.senses.find_ocr import FakeOCR


@pytest.fixture(autouse=True)
def _seam_screen(monkeypatch):
    """Route the screen seam at the (patched) macOS screen module so this
    OS-agnostic test runs on Windows too (prod resolves via backends.build_screen,
    which off macOS would return screen_win and bypass the patch)."""
    import daimon.backends as backends
    import daimon.capture.screen as screen
    monkeypatch.setattr(backends, "build_screen", lambda: screen)


class _FakeExclusions:
    def evaluate_frontmost(self, bundle):
        class _G:
            refused = False
            reason = ""
        return _G()

    def redact_image(self, image):
        return image

    def is_target_secret(self, role=None):
        return False


class _ToolReg:
    def __init__(self):
        self.tools = {}

    def tool(self, name, description=""):
        def deco(fn):
            self.tools[name] = fn
            return fn
        return deco


# left display: origin -1920, snapshot downscaled source 1920 -> image 1600
_DISPLAYS = [
    Display(index=0, display_id=1, width=1920, height=1080, is_main=True,
            origin_x=0, origin_y=0, dpi=96),
    Display(index=1, display_id=2, width=1920, height=1080, is_main=False,
            origin_x=-1920, origin_y=0, dpi=96),
]

_WORDS = [
    WordBox(text="Etat_FACTURE", x=40, y=120, width=110, height=20),
    WordBox(text="Etat_FACTURECLIENT", x=40, y=160, width=180, height=22),
    WordBox(text="Valider", x=300, y=400, width=70, height=24),
]


def _fake_frame(display_index):
    d = _DISPLAYS[display_index]
    # a snapshot of the left display taken at max_width=1600 (scale 1600/1920)
    return Frame(
        image=object(),
        width=1600,
        height=900,
        display_index=display_index,
        frontmost_bundle_id="com.windev.app",
        display_origin_x=d.origin_x,
        display_origin_y=d.origin_y,
        physical_width=1920,
        physical_height=1080,
        image_scale=1600 / 1920,
        region=None,
        dpi=96,
    )


def _register(monkeypatch, words=_WORDS):
    import daimon.capture.screen as screen
    monkeypatch.setattr(screen, "list_displays", lambda: _DISPLAYS)
    monkeypatch.setattr(
        screen, "capture_display",
        lambda display_index=0, max_width=720, region=None: _fake_frame(display_index),
    )
    from daimon.senses.vue import Vue
    reg = _ToolReg()
    Vue(_FakeExclusions(), ocr=FakeOCR(words)).register(reg)
    return reg


# --- vue_find: locate a label and return clickable global coords ------------


def test_vue_find_returns_global_coords_for_label(monkeypatch):
    reg = _register(monkeypatch)
    out = reg.tools["vue_find"](text="Etat_FACTURECLIENT", display=1, max_width=1600)
    assert out["found"] is True
    assert out["text"] == "Etat_FACTURECLIENT"
    # box centre in image px -> deterministic global via AXE 1
    from daimon.capture.coordspace import CoordSpace
    cs = CoordSpace(display_origin_x=-1920, display_origin_y=0, image_scale=1600 / 1920)
    icx, icy = WordBox(text="", x=40, y=160, width=180, height=22).center()
    assert (out["global_x"], out["global_y"]) == cs.to_global(icx, icy)


def test_vue_find_round_trips_through_main_click(monkeypatch):
    # The DoD: the coords vue_find returns, passed to main_click (global space),
    # resolve to the same pixel — i.e. they land on the label. We reuse the
    # server's own resolver so this is the real click path, not a re-derivation.
    reg = _register(monkeypatch)
    out = reg.tools["vue_find"](text="Etat_FACTURECLIENT", display=1, max_width=1600)

    from daimon.server import _resolve_point
    # main_click(space='global') passes coords straight through to the actuator.
    gx, gy = _resolve_point(out["global_x"], out["global_y"], None, "global")
    assert (gx, gy) == (out["global_x"], out["global_y"])
    # and they map back onto the label's box in image space
    from daimon.capture.coordspace import CoordSpace
    cs = CoordSpace(display_origin_x=-1920, display_origin_y=0, image_scale=1600 / 1920)
    bx, by = cs.to_image(gx, gy)
    label = WordBox(text="", x=40, y=160, width=180, height=22)
    assert label.x <= bx <= label.x + label.width
    assert label.y <= by <= label.y + label.height


def test_vue_find_not_found_reports_cleanly(monkeypatch):
    reg = _register(monkeypatch)
    out = reg.tools["vue_find"](text="no-such-label-zzz", display=1, max_width=1600)
    assert out["found"] is False
    assert out["global_x"] is None
    assert "candidates" in out  # surfaces what WAS on screen, to help retry


def test_vue_find_lists_near_candidates_on_miss(monkeypatch):
    reg = _register(monkeypatch)
    # below-threshold query (no substring hit, only weak char overlap): not
    # found, but the closest siblings are surfaced so the pilot can retry.
    out = reg.tools["vue_find"](text="Etat_zz", display=1, max_width=1600)
    assert out["found"] is False
    assert any("Etat_FACTURE" in c for c in out["candidates"])


def test_vue_find_refused_when_app_excluded(monkeypatch):
    import daimon.capture.screen as screen
    monkeypatch.setattr(screen, "list_displays", lambda: _DISPLAYS)
    monkeypatch.setattr(
        screen, "capture_display",
        lambda display_index=0, max_width=720, region=None: _fake_frame(display_index),
    )

    class _Refusing(_FakeExclusions):
        def evaluate_frontmost(self, bundle):
            class _G:
                refused = True
                reason = "secret app frontmost"
            return _G()

    from daimon.senses.vue import Vue
    reg = _ToolReg()
    Vue(_Refusing(), ocr=FakeOCR(_WORDS)).register(reg)
    with pytest.raises(PermissionError):
        reg.tools["vue_find"](text="Valider", display=1, max_width=1600)
