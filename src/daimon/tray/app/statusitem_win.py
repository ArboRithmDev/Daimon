"""Windows system-tray controller (QSystemTrayIcon).

The Windows twin of the macOS NSStatusItem controller. Renders the SAME pure
``menu_model.build_menu(gather())`` into a Qt menu and routes each action_id —
so the menu structure and most handlers are shared; only the rendering (Qt), the
folder-open (``os.startfile``), the onboarding window (Qt), and quit
(``QApplication.quit``) differ from macOS.
"""

from __future__ import annotations


class WindowsTrayController:
    def __init__(self) -> None:
        self._app = None
        self._tray = None
        self._menu = None       # the persistent context menu, refreshed on open
        self._onboard = None

    def install(self, app) -> None:
        from PySide6 import QtWidgets

        self._app = app
        self._tray = QtWidgets.QSystemTrayIcon()
        self._tray.setIcon(self._icon())
        self._tray.setToolTip("Daimon")

        # One persistent menu, repopulated each time it is about to open. A
        # periodic setContextMenu() would replace the menu WHILE it is open and
        # dismiss it after a couple of seconds (the "menu closes itself" bug).
        self._menu = QtWidgets.QMenu()
        self._menu.aboutToShow.connect(self._refresh)
        self._refresh()
        self._tray.setContextMenu(self._menu)
        self._tray.show()

    def _icon(self):
        from pathlib import Path

        from PySide6 import QtGui

        assets = Path(__file__).resolve().parents[2] / "assets"
        for name in ("menubar-glyph@2x.png", "menubar-glyph.png"):
            p = assets / name
            if p.exists():
                return QtGui.QIcon(str(p))
        # Fallback: a simple cyan aperture dot.
        pm = QtGui.QPixmap(18, 18)
        pm.fill(QtGui.QColor(0, 0, 0, 0))
        painter = QtGui.QPainter(pm)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setPen(QtGui.Qt.NoPen)
        painter.setBrush(QtGui.QColor(0, 200, 255))
        painter.drawEllipse(2, 2, 14, 14)
        painter.end()
        return QtGui.QIcon(pm)

    def _refresh(self) -> None:
        """Repopulate the persistent menu with fresh state (called on open)."""
        from ..menu_model import build_menu
        from ..state import gather
        try:
            items = build_menu(gather())
        except Exception:
            from ...applog import log_exception
            log_exception("tray/_refresh")
            return
        self._menu.clear()
        self._fill(self._menu, items)

    def _fill(self, menu, items) -> None:
        for item in items:
            if item.kind == "separator":
                menu.addSeparator()
                continue
            if item.kind == "submenu":
                sub = menu.addMenu(item.label)
                self._fill(sub, list(item.children))
                continue
            act = menu.addAction(item.label)
            if item.kind == "label":
                act.setEnabled(False)
                continue
            act.setEnabled(item.enabled)
            if item.kind in ("checkbox", "radio"):
                act.setCheckable(True)
                act.setChecked(item.checked)
            aid = item.action_id
            act.triggered.connect(lambda _checked=False, a=aid: self._dispatch(a))

    def _dispatch(self, action_id: str) -> None:
        try:
            self._route(action_id)
        except Exception:
            from ...applog import log_exception
            log_exception(action_id)

    def _route(self, action_id: str) -> None:
        from ...config import _MOTOR_DEFAULT, _OVERLAY_DEFAULT
        from ..settings import set_ceiling, set_overlay

        if action_id.startswith("set_ceiling:"):
            set_ceiling(action_id.split(":", 1)[1], _MOTOR_DEFAULT)
            self._refresh()
        elif action_id == "toggle_overlay":
            from ..state import gather
            set_overlay(not gather().overlay_on, _OVERLAY_DEFAULT)
            self._refresh()
        elif action_id == "install_all":
            from ...setup.deploy import install_all
            install_all()
            self._refresh()
        elif action_id.startswith("toggle_client:"):
            name = action_id.split(":", 1)[1]
            from ...setup.clients import base
            from ...setup.clients.registry import default_adapters, detected
            from ...setup.invocation import daimon_command
            adapter = next((a for a in detected(default_adapters()) if a.name == name), None)
            if adapter is not None:
                if base.status(adapter, "daimon").action == "present":
                    base.uninstall(adapter, "daimon")
                else:
                    base.install(adapter, "daimon", daimon_command())
            self._refresh()
        elif action_id == "run_setup":
            from ...setup.gui.window_win import OnboardingController
            self._onboard = OnboardingController()
            self._onboard.show()
        elif action_id == "open_config":
            self._open_folder("config")
        elif action_id == "open_logs":
            self._open_folder("logs")
        elif action_id == "quit":
            if self._app is not None:
                self._app.quit()

    def _open_folder(self, which: str) -> None:
        import os
        from ...userdata import config_dir, logs_dir
        d = config_dir() if which == "config" else logs_dir()
        d.mkdir(parents=True, exist_ok=True)
        os.startfile(str(d))  # noqa: S606 — open the folder in Explorer


def main() -> int:
    from PySide6 import QtWidgets

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    app.setQuitOnLastWindowClosed(False)  # resident tray app, no main window
    controller = WindowsTrayController()
    controller.install(app)
    app.exec()
    return 0
