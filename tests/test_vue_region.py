from daimon.capture.screen import crop_region


class _Img:
    def __init__(self, w, h): self.width, self.height = w, h; self.box = None
    def crop(self, box): self.box = box; return self


def test_crop_region_clamps_to_bounds():
    img = _Img(1000, 800)
    out = crop_region(img, {"x": 100, "y": 50, "width": 5000, "height": 5000})
    assert out.box == (100, 50, 1000, 800)


def test_crop_region_none_is_identity():
    img = _Img(10, 10)
    assert crop_region(img, None) is img
