"""Windows tray menu construction — offscreen Qt, no display. Windows-only."""

import os
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows-only tray")
pytest.importorskip("PySide6")

# Render Qt without a display so the test is headless-safe.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _state():
    from daimon.motor.types import Level
    from daimon.tray.state import TrayState
    return TrayState(
        version="0.0.3", screen_ok=True, accessibility_ok=True,
        clients=(), ceiling=Level.READ, l4_active=False, overlay_on=False,
    )


def test_tray_menu_builds_from_pure_model():
    from PySide6 import QtWidgets

    from daimon.tray.app.statusitem_win import WindowsTrayController
    from daimon.tray.menu_model import build_menu

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    ctrl = WindowsTrayController()  # keep a ref so connected lambdas survive
    menu = QtWidgets.QMenu()
    ctrl._fill(menu, build_menu(_state()))

    texts = [a.text() for a in menu.actions()]
    assert any("Daimon v0.0.3" in t for t in texts)
    assert any("Quit Daimon" in t for t in texts)
    assert any(t.startswith("Hands ceiling:") for t in texts)   # ceiling submenu
    assert any(t.startswith("Clients (") for t in texts)        # clients submenu
    assert any("Show overlay" in t for t in texts)
    del app  # keep the QApplication alive until here


def test_tray_icon_is_the_coloured_duo_glyph():
    # On the Windows tray the brand must render in its real presence-purple +
    # companion-amber colours — the macOS black template glyph is near-invisible
    # on a dark notification area.
    from pathlib import Path

    from PySide6 import QtWidgets

    import daimon
    from daimon.tray.app.statusitem_win import WindowsTrayController

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])

    duo = Path(daimon.__file__).resolve().parent / "assets" / "tray-glyph-duo.svg"
    assert duo.exists(), "the coloured Duo tray glyph must ship"

    icon = WindowsTrayController._svg_icon(duo)
    assert icon is not None and not icon.isNull()

    img = icon.pixmap(64, 64).toImage()
    coloured = sum(
        1
        for y in range(img.height())
        for x in range(img.width())
        if (c := img.pixelColor(x, y)).alpha() > 0
        and (c.red() + c.green() + c.blue()) > 180
    )
    assert coloured > 100, "the lobes must render in colour, not black"
    del app
