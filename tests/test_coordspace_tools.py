"""Tool-level coord-space wiring: display-relative resolution + snapshot contract.

These exercise the seams (resolver + vue tools) with fake displays/captures —
no real screen, no OS click.
"""

import json

import pytest

from daimon.capture.screen import Display, Frame


# --- fake topology: a main display + one physically to its LEFT (negative origin)
_DISPLAYS = [
    Display(index=0, display_id=1, width=1920, height=1080, is_main=True,
            origin_x=0, origin_y=0, dpi=96),
    Display(index=1, display_id=2, width=1920, height=1080, is_main=False,
            origin_x=-1920, origin_y=0, dpi=96),
]


# ---------------------------------------------------------------- _resolve_point


def test_resolve_point_global_space_passthrough():
    from daimon.server import _resolve_point
    assert _resolve_point(10, 20, display=None, space="global") == (10, 20)


def test_resolve_point_image_space_main_display(monkeypatch):
    import daimon.capture.screen as screen
    from daimon import server
    monkeypatch.setattr(screen, "list_displays", lambda: _DISPLAYS)
    # snapshot at max_width=1600 of a 1920 display -> scale 1600/1920
    gx, gy = server._resolve_point(800, 0, display=0, space="image", max_width=1600)
    assert (gx, gy) == (960, 0)  # 800 / (1600/1920) = 960, origin 0


def test_resolve_point_image_space_negative_display(monkeypatch):
    import daimon.capture.screen as screen
    from daimon import server
    monkeypatch.setattr(screen, "list_displays", lambda: _DISPLAYS)
    # The field bug, now solved internally: left display, downscaled snapshot.
    gx, gy = server._resolve_point(1600, 0, display=1, space="image", max_width=1600)
    # image right edge -> source 1920 -> global -1920 + 1920 = 0
    assert (gx, gy) == (0, 0)
    gx0, _ = server._resolve_point(0, 0, display=1, space="image", max_width=1600)
    assert gx0 == -1920


def test_resolve_point_image_space_no_downscale(monkeypatch):
    import daimon.capture.screen as screen
    from daimon import server
    monkeypatch.setattr(screen, "list_displays", lambda: _DISPLAYS)
    # max_width >= display width -> scale 1.0, pure offset on the left display
    gx, gy = server._resolve_point(100, 50, display=1, space="image", max_width=3000)
    assert (gx, gy) == (-1820, 50)


def test_resolve_point_image_requires_display():
    from daimon.server import _resolve_point
    with pytest.raises(ValueError):
        _resolve_point(10, 20, display=None, space="image")


def test_resolve_point_image_with_region(monkeypatch):
    import daimon.capture.screen as screen
    from daimon import server
    monkeypatch.setattr(screen, "list_displays", lambda: _DISPLAYS)
    region = {"x": 200, "y": 300, "width": 800, "height": 600}
    # source_w=800, max_width=400 -> scale 0.5 ; image (100,50) -> source (200,100)
    # global = origin(-1920,0) + region(200,300) + source(200,100)
    gx, gy = server._resolve_point(100, 50, display=1, space="image",
                                   max_width=400, region=region)
    assert (gx, gy) == (-1920 + 200 + 200, 0 + 300 + 100)


# ---------------------------------------------------------------- vue tools


class _FakeExclusions:
    def evaluate_frontmost(self, bundle):
        class _G:
            refused = False
            reason = ""
        return _G()

    def redact_image(self, image):
        return image


class _FakeImage:
    width, height = 1600, 900

    def save(self, buf, format):
        buf.write(b"\x89PNG-fake")


def _fake_frame():
    return Frame(
        image=_FakeImage(), width=1600, height=900, display_index=1,
        frontmost_bundle_id=None, display_origin_x=-1920, display_origin_y=0,
        physical_width=1920, physical_height=1080, image_scale=1600 / 1920,
        region=None, dpi=96,
    )


def _make_vue():
    from daimon.senses.vue import Vue
    return Vue(_FakeExclusions())


class _ToolReg:
    """Captures @mcp.tool-decorated functions by name for direct invocation."""
    def __init__(self):
        self.tools = {}

    def tool(self, name, description=""):
        def deco(fn):
            self.tools[name] = fn
            return fn
        return deco


def test_vue_displays_exposes_origin_and_dpi(monkeypatch):
    import daimon.capture.screen as screen
    monkeypatch.setattr(screen, "list_displays", lambda: _DISPLAYS)
    reg = _ToolReg()
    _make_vue().register(reg)
    out = reg.tools["vue_displays"]()
    assert out[1] == {
        "index": 1, "width": 1920, "height": 1080, "is_main": False,
        "origin": {"x": -1920, "y": 0}, "dpi": 96,
    }


def test_vue_snapshot_returns_contract_then_image(monkeypatch):
    import daimon.capture.screen as screen
    monkeypatch.setattr(screen, "capture_display",
                        lambda display_index, max_width, region: _fake_frame())
    reg = _ToolReg()
    vue = _make_vue()
    # stub the secret-rect probe so redaction is a clean no-op
    monkeypatch.setattr(vue, "_secret_rects", lambda b: [])
    vue.register(reg)
    blocks = reg.tools["vue_snapshot"](display=1, max_width=1600)
    assert len(blocks) == 2
    text, image = blocks
    contract = json.loads(text.text)["coord_space"]
    assert contract == {
        "display_index": 1,
        "display_origin": {"x": -1920, "y": 0},
        "physical_size": {"w": 1920, "h": 1080},
        "image_size": {"w": 1600, "h": 900},
        "image_scale": 1600 / 1920,
        "region": None,
        "dpi": 96,
    }
    # image block is the PNG
    assert getattr(image, "data", None) or getattr(image, "_data", None)


def test_vue_resolve_round_trips(monkeypatch):
    import daimon.capture.screen as screen
    monkeypatch.setattr(screen, "list_displays", lambda: _DISPLAYS)
    reg = _ToolReg()
    _make_vue().register(reg)
    resolve = reg.tools["vue_resolve"]
    fwd = resolve(display=1, max_width=1600, image_x=1600, image_y=0)
    assert fwd == {"global_x": 0, "global_y": 0}
    back = resolve(display=1, max_width=1600, global_x=0, global_y=0)
    assert back == {"image_x": 1600, "image_y": 0}


def test_vue_resolve_needs_a_pair(monkeypatch):
    import daimon.capture.screen as screen
    monkeypatch.setattr(screen, "list_displays", lambda: _DISPLAYS)
    reg = _ToolReg()
    _make_vue().register(reg)
    with pytest.raises(ValueError):
        reg.tools["vue_resolve"](display=0)
