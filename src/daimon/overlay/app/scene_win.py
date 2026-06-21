"""Scene — applies overlay protocol commands to the Qt canvas (Windows).

The Windows twin of the macOS CoreAnimation ``Scene``. Pure dispatch: it maps
each protocol command to a canvas mutation, so it is unit-testable with a fake
canvas and no Qt. The OverlayServer calls ``apply`` on the GUI thread via its
main_dispatch seam.
"""

from __future__ import annotations


class Scene:
    def __init__(self, canvas) -> None:
        self._canvas = canvas

    def apply(self, cmd) -> None:
        name = type(cmd).__name__
        c = self._canvas
        if name == "Clear":
            c.clear_all()
        elif name == "Highlight":
            c.set_highlight(cmd.x, cmd.y, cmd.w, cmd.h, cmd.label, cmd.style)
        elif name == "Spotlight":
            c.set_spotlight(cmd.x, cmd.y, cmd.w, cmd.h)
        elif name == "Cursor":
            c.set_cursor(cmd.x, cmd.y)
        elif name == "Ripple":
            c.add_ripple(cmd.x, cmd.y)
        elif name == "Banner":
            c.set_banner(cmd.text, cmd.level)
        # unknown commands are ignored (forward-compatible)
