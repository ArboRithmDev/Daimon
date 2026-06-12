from daimon.exclusions import black_out_rects


class _Draw:
    def __init__(self): self.rects = []
    def rectangle(self, box, fill): self.rects.append(box)


class _Img:
    def __init__(self): self.draw = _Draw()


def test_black_out_rects_draws_each(monkeypatch):
    import daimon.exclusions as ex
    img = _Img()
    monkeypatch.setattr(ex, "_image_draw", lambda image: img.draw)
    black_out_rects(img, [{"x": 1, "y": 2, "width": 3, "height": 4}])
    assert img.draw.rects == [(1, 2, 4, 6)]


def test_black_out_empty_is_noop(monkeypatch):
    import daimon.exclusions as ex
    img = _Img()
    monkeypatch.setattr(ex, "_image_draw", lambda image: img.draw)
    black_out_rects(img, [])
    assert img.draw.rects == []
