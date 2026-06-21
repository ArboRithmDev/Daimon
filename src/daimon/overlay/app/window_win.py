"""Transparent, click-through, capture-invisible overlay canvas (Windows/Qt).

A frameless, always-on-top, translucent ``QWidget`` that covers the primary
screen and never takes input (``WindowTransparentForInput`` +
``WA_TransparentForMouseEvents``). It is removed from screen capture via
``SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)`` (Windows 10 2004+), the
twin of macOS ``NSWindowSharingNone`` — so Daimon's own overlay never self-films.

The canvas holds the current drawables (highlight / spotlight / cursor / ripples
/ banner) and paints them; the Scene mutates this state. Ripples animate on a
timer. All mutation must happen on the GUI thread (the server marshals via its
main_dispatch seam).
"""

from __future__ import annotations

_WDA_EXCLUDEFROMCAPTURE = 0x00000011

# Per-style stroke colours (RGBA). Mirrors the intent of the macOS theme.
_STYLE_RGBA = {
    "default": (0, 200, 255, 230),
    "L1": (0, 200, 255, 230),
    "L2": (255, 190, 0, 235),
    "L3": (255, 90, 60, 240),
    "gate": (255, 60, 60, 255),
}


def _exclude_from_capture(hwnd: int) -> None:
    import ctypes
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.SetWindowDisplayAffinity(wintypes.HWND(hwnd), wintypes.DWORD(_WDA_EXCLUDEFROMCAPTURE))


def make_overlay_canvas(anti_feedback: bool = True, opacity: float = 0.95):
    """Build + show the overlay canvas. A QApplication must already exist."""
    from PySide6 import QtCore, QtGui

    canvas = _build_canvas_class()()
    canvas.setWindowFlags(
        QtCore.Qt.FramelessWindowHint
        | QtCore.Qt.WindowStaysOnTopHint
        | QtCore.Qt.Tool
        | QtCore.Qt.WindowTransparentForInput
    )
    canvas.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
    canvas.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
    canvas.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
    geo = QtGui.QGuiApplication.primaryScreen().geometry()
    canvas.setGeometry(geo)
    canvas.setWindowOpacity(opacity)
    canvas.show()
    if anti_feedback:
        try:
            _exclude_from_capture(int(canvas.winId()))
        except Exception:
            pass  # capture-exclusion is best-effort (needs Win10 2004+)
    return canvas


def _build_canvas_class():
    from PySide6 import QtCore, QtGui, QtWidgets

    class _OverlayCanvas(QtWidgets.QWidget):
        def __init__(self):
            super().__init__()
            self._highlight = None   # (x, y, w, h, label, style)
            self._spotlight = None   # (x, y, w, h)
            self._cursor = None      # (x, y)
            self._banner = None      # (text, level)
            self._ripples = []       # list of [x, y, progress]
            self._timer = QtCore.QTimer(self)
            self._timer.setInterval(33)  # ~30 fps
            self._timer.timeout.connect(self._tick)

        # -- state setters (GUI thread) --
        def clear_all(self):
            self._highlight = self._spotlight = self._cursor = self._banner = None
            self._ripples.clear()
            self.update()

        def set_highlight(self, x, y, w, h, label, style):
            self._highlight = (x, y, w, h, label, style)
            self.update()

        def set_spotlight(self, x, y, w, h):
            self._spotlight = (x, y, w, h)
            self.update()

        def set_cursor(self, x, y):
            self._cursor = (x, y)
            self.update()

        def set_banner(self, text, level):
            self._banner = (text, level)
            self.update()

        def add_ripple(self, x, y):
            self._ripples.append([x, y, 0.0])
            if not self._timer.isActive():
                self._timer.start()
            self.update()

        def _tick(self):
            for r in self._ripples:
                r[2] += 0.08
            self._ripples = [r for r in self._ripples if r[2] < 1.0]
            if not self._ripples:
                self._timer.stop()
            self.update()

        # -- painting --
        def paintEvent(self, _event):
            p = QtGui.QPainter(self)
            p.setRenderHint(QtGui.QPainter.Antialiasing, True)

            if self._spotlight is not None:
                x, y, w, h = self._spotlight
                path = QtGui.QPainterPath()
                path.addRect(QtCore.QRectF(self.rect()))
                hole = QtGui.QPainterPath()
                hole.addRoundedRect(QtCore.QRectF(x, y, w, h), 8, 8)
                p.fillPath(path.subtracted(hole), QtGui.QColor(0, 0, 0, 140))

            if self._highlight is not None:
                x, y, w, h, label, style = self._highlight
                r, g, b, a = _STYLE_RGBA.get(style, _STYLE_RGBA["default"])
                pen = QtGui.QPen(QtGui.QColor(r, g, b, a))
                pen.setWidth(3)
                p.setPen(pen)
                p.setBrush(QtCore.Qt.NoBrush)
                p.drawRoundedRect(QtCore.QRectF(x, y, w, h), 8, 8)
                if label:
                    p.setPen(QtGui.QColor(255, 255, 255, 235))
                    p.drawText(int(x), int(y) - 6, label)

            for x, y, prog in self._ripples:
                radius = 8 + prog * 40
                alpha = int(220 * (1.0 - prog))
                pen = QtGui.QPen(QtGui.QColor(0, 200, 255, alpha))
                pen.setWidth(2)
                p.setPen(pen)
                p.setBrush(QtCore.Qt.NoBrush)
                p.drawEllipse(QtCore.QPointF(x, y), radius, radius)

            if self._cursor is not None:
                x, y = self._cursor
                p.setPen(QtCore.Qt.NoPen)
                p.setBrush(QtGui.QColor(0, 200, 255, 120))
                p.drawEllipse(QtCore.QPointF(x, y), 14, 14)

            if self._banner is not None:
                text, _level = self._banner
                p.setPen(QtGui.QColor(255, 255, 255, 240))
                p.setBrush(QtGui.QColor(0, 0, 0, 160))
                metrics = p.fontMetrics()
                tw = metrics.horizontalAdvance(text) + 24
                p.drawRoundedRect(QtCore.QRectF(20, 20, tw, 34), 6, 6)
                p.drawText(QtCore.QRectF(20, 20, tw, 34), QtCore.Qt.AlignCenter, text)
            p.end()

    return _OverlayCanvas
