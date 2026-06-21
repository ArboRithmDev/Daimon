"""Pure dispatch tests for the Windows overlay Scene — run on every platform."""

from daimon.overlay.app.scene_win import Scene
from daimon.overlay.protocol import Banner, Clear, Cursor, Highlight, Ripple, Spotlight


class _FakeCanvas:
    def __init__(self):
        self.calls = []

    def clear_all(self): self.calls.append(("clear",))
    def set_highlight(self, *a): self.calls.append(("highlight", a))
    def set_spotlight(self, *a): self.calls.append(("spotlight", a))
    def set_cursor(self, *a): self.calls.append(("cursor", a))
    def set_banner(self, *a): self.calls.append(("banner", a))
    def add_ripple(self, *a): self.calls.append(("ripple", a))


def test_each_command_maps_to_a_canvas_call():
    c = _FakeCanvas()
    s = Scene(c)
    s.apply(Highlight(x=1, y=2, w=3, h=4, label="x", style="L2"))
    s.apply(Spotlight(x=5, y=6, w=7, h=8))
    s.apply(Cursor(x=9, y=10))
    s.apply(Ripple(x=11, y=12))
    s.apply(Banner(text="hi", level="L1"))
    s.apply(Clear())
    kinds = [c0[0] for c0 in c.calls]
    assert kinds == ["highlight", "spotlight", "cursor", "ripple", "banner", "clear"]
    assert c.calls[0][1] == (1, 2, 3, 4, "x", "L2")
