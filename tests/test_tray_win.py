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
