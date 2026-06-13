"""Core-Animation scene: applies overlay protocol commands to CALayers."""

from __future__ import annotations

from ..theme import style_for


class Scene:
    def __init__(self, layer, height: float = 0):
        self._root = layer
        self._h = height
        self._nodes = {}   # keyed transient layers

    def _nscolor(self, rgba, opacity=1.0):
        from AppKit import NSColor
        r, g, b, a = rgba
        return NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, a * opacity).CGColor()

    def apply(self, cmd) -> None:
        getattr(self, f"_do_{cmd.cmd}", self._noop)(cmd)

    def _noop(self, cmd): pass

    def _do_highlight(self, cmd):
        import Quartz
        st = style_for(cmd.style)
        h = self._nodes.get("highlight") or Quartz.CAShapeLayer.layer()
        h.setFrame_(((cmd.x, cmd.y), (cmd.w, cmd.h)))
        h.setCornerRadius_(st["radius"])
        h.setBorderWidth_(2.5)
        h.setBorderColor_(self._nscolor(st["rgba"]))
        h.setBackgroundColor_(self._nscolor(st["rgba"], 0.08))
        if "highlight" not in self._nodes:
            self._root.addSublayer_(h); self._nodes["highlight"] = h
        if st["pulse"]:
            self._pulse(h, st["duration"])

    def _do_spotlight(self, cmd):
        pass  # vignette mask — premium; drawn as a dimmed full-screen layer with a clear hole

    def _do_cursor(self, cmd):
        import Quartz
        c = self._nodes.get("cursor") or Quartz.CALayer.layer()
        c.setFrame_(((cmd.x - 12, cmd.y - 12), (24, 24)))
        c.setCornerRadius_(12)
        c.setBackgroundColor_(self._nscolor((0.25, 0.55, 0.95, 1.0), 0.25))
        if "cursor" not in self._nodes:
            self._root.addSublayer_(c); self._nodes["cursor"] = c

    def _do_ripple(self, cmd):
        import Quartz
        r = Quartz.CALayer.layer()
        r.setFrame_(((cmd.x - 4, cmd.y - 4), (8, 8)))
        r.setCornerRadius_(4)
        r.setBackgroundColor_(self._nscolor((0.25, 0.55, 0.95, 1.0)))
        self._root.addSublayer_(r)
        Quartz.CATransaction.begin()
        Quartz.CATransaction.setCompletionBlock_(lambda: r.removeFromSuperlayer())
        self._ripple(r)
        Quartz.CATransaction.commit()

    def _do_banner(self, cmd):
        import Quartz
        from ..theme import style_for as sf
        t = self._nodes.get("banner") or Quartz.CATextLayer.layer()
        t.setString_(cmd.text)
        t.setFontSize_(13)
        t.setForegroundColor_(self._nscolor((1, 1, 1, 1)))
        t.setBackgroundColor_(self._nscolor(sf(cmd.level)["rgba"], 0.85))
        t.setCornerRadius_(8)
        t.setMasksToBounds_(True)
        t.setAlignmentMode_("center")
        y_pos = (self._h - 60) if self._h > 0 else 40
        t.setFrame_(((40, y_pos), (480, 28)))
        if "banner" not in self._nodes:
            self._root.addSublayer_(t); self._nodes["banner"] = t

    def _do_clear(self, cmd):
        for layer in list(self._nodes.values()):
            layer.removeFromSuperlayer()
        self._nodes.clear()

    def _pulse(self, layer, duration):
        import Quartz
        a = Quartz.CABasicAnimation.animationWithKeyPath_("opacity")
        a.setFromValue_(1.0); a.setToValue_(0.45)
        a.setDuration_(duration); a.setAutoreverses_(True); a.setRepeatCount_(1e9)
        layer.addAnimation_forKey_(a, "pulse")

    def _ripple(self, layer):
        import Quartz
        grow = Quartz.CABasicAnimation.animationWithKeyPath_("transform.scale")
        grow.setFromValue_(1.0); grow.setToValue_(6.0); grow.setDuration_(0.5)
        fade = Quartz.CABasicAnimation.animationWithKeyPath_("opacity")
        fade.setFromValue_(0.8); fade.setToValue_(0.0); fade.setDuration_(0.5)
        layer.addAnimation_forKey_(grow, "grow")
        layer.addAnimation_forKey_(fade, "fade")
