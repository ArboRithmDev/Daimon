"""Pure reprojection math — no OS, no screen. The deterministic coord-space core."""

import pytest

from daimon.capture.coordspace import (
    CoordSpace,
    coord_space_contract,
    coord_space_from_frame,
)


def test_identity_no_offset_no_scale():
    cs = CoordSpace(display_origin_x=0, display_origin_y=0, image_scale=1.0)
    assert cs.to_global(100, 50) == (100, 50)
    assert cs.to_image(100, 50) == (100, 50)


def test_downscale_only():
    # 1920 source captured at max_width=1600 -> scale 1600/1920 = 0.8333…
    cs = CoordSpace(display_origin_x=0, display_origin_y=0, image_scale=1600 / 1920)
    # an image pixel at x=800 maps to source 800 / 0.8333 = 960
    assert cs.to_global(800, 0) == (960, 0)


def test_negative_origin_left_display():
    # The field bug: a display physically left of main has origin -1920.
    # global_x = -1920 + image_x / scale ; scale = 1600/1920
    cs = CoordSpace(display_origin_x=-1920, display_origin_y=0, image_scale=1600 / 1920)
    gx, gy = cs.to_global(1600, 0)
    # image right edge (1600) -> source 1920 -> global -1920 + 1920 = 0
    assert (gx, gy) == (0, 0)
    # the documented formula global_x = image_x*(1920/1600) - 1920
    assert cs.to_global(0, 0) == (-1920, 0)


def test_region_offset_added():
    cs = CoordSpace(display_origin_x=100, display_origin_y=200, image_scale=1.0,
                    region_x=30, region_y=40)
    # global = origin + region + image/scale
    assert cs.to_global(10, 10) == (140, 250)


def test_region_and_scale_and_negative_origin_compose():
    cs = CoordSpace(display_origin_x=-1920, display_origin_y=-100, image_scale=0.5,
                    region_x=200, region_y=300)
    gx, gy = cs.to_global(50, 80)
    # x: -1920 + 200 + 50/0.5 = -1920 + 200 + 100 = -1620
    # y: -100 + 300 + 80/0.5 = -100 + 300 + 160 = 360
    assert (gx, gy) == (-1620, 360)


@pytest.mark.parametrize("scale", [1.0, 0.8333, 0.5, 1600 / 1920])
@pytest.mark.parametrize("origin", [(0, 0), (-1920, 0), (1920, -1080), (200, 300)])
@pytest.mark.parametrize("region", [(0, 0), (37, 51)])
def test_round_trip_is_exact(scale, origin, region):
    cs = CoordSpace(display_origin_x=origin[0], display_origin_y=origin[1],
                    image_scale=scale, region_x=region[0], region_y=region[1])
    for ix, iy in [(0, 0), (10, 10), (640, 480), (1599, 899)]:
        gx, gy = cs.to_global(ix, iy)
        back = cs.to_image(gx, gy)
        # exact within rounding (sub-pixel from integer global coords)
        assert abs(back[0] - ix) <= 1 and abs(back[1] - iy) <= 1


class _FakeFrame:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_coord_space_from_frame_reads_region():
    f = _FakeFrame(display_origin_x=-1920, display_origin_y=0, image_scale=0.5,
                   region={"x": 10, "y": 20, "width": 100, "height": 100})
    cs = coord_space_from_frame(f)
    assert cs.region_x == 10 and cs.region_y == 20
    assert cs.to_global(50, 50) == (-1920 + 10 + 100, 0 + 20 + 100)


def test_coord_space_from_frame_none_region():
    f = _FakeFrame(display_origin_x=0, display_origin_y=0, image_scale=1.0, region=None)
    cs = coord_space_from_frame(f)
    assert cs.region_x == 0 and cs.region_y == 0


def test_contract_shape_matches_annexe_a():
    f = _FakeFrame(display_index=0, display_origin_x=-1920, display_origin_y=0,
                   physical_width=1920, physical_height=1080,
                   width=1600, height=900, image_scale=0.8333, region=None, dpi=96)
    c = coord_space_contract(f)
    assert c == {
        "display_index": 0,
        "display_origin": {"x": -1920, "y": 0},
        "physical_size": {"w": 1920, "h": 1080},
        "image_size": {"w": 1600, "h": 900},
        "image_scale": 0.8333,
        "region": None,
        "dpi": 96,
    }
