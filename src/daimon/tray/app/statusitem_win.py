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
        self._update_state = None   # menu_model.UpdateMenuState | None
        self._update_info = None    # the resolved UpdateInfo to apply
        self._update_bridge = None
        self._update_timer = None

    def install(self, app) -> None:
        from PySide6 import QtCore, QtWidgets

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

        # Auto-update: check shortly after start, then on the configured interval.
        # The network check runs off the GUI thread; results marshal back via a
        # queued signal (the bridge lives on the GUI thread).
        class _Bridge(QtCore.QObject):
            result = QtCore.Signal(object)
        self._update_bridge = _Bridge()
        self._update_bridge.result.connect(self._on_update_result)

        from ...config import load_update_config
        cfg = load_update_config()
        if cfg.enabled:
            QtCore.QTimer.singleShot(4000, self._start_update_check)
            self._update_timer = QtCore.QTimer()
            self._update_timer.setInterval(int(max(1.0, cfg.interval_hours) * 3600 * 1000))
            self._update_timer.timeout.connect(self._start_update_check)
            self._update_timer.start()

    def _icon(self):
        from pathlib import Path

        from PySide6 import QtGui

        assets = Path(__file__).resolve().parents[2] / "assets"

        # Preferred: the COLOURED Duo glyph. The macOS menu-bar PNGs are a black
        # template tinted by the OS; on the Windows tray (often a dark surface)
        # that black glyph is near-invisible, so we render the brand SVG in its
        # real presence-purple + companion-amber colours — readable on a light
        # or dark tray alike.
        duo = assets / "tray-glyph-duo.svg"
        if duo.exists():
            icon = self._svg_icon(duo)
            if icon is not None:
                return icon

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

    @staticmethod
    def _svg_icon(svg_path):
        """Rasterize a brand SVG into a multi-size QIcon. None if QtSvg is absent
        or the render fails (caller falls back to the PNG glyph)."""
        try:
            from PySide6 import QtGui
            from PySide6.QtCore import Qt
            from PySide6.QtSvg import QSvgRenderer

            renderer = QSvgRenderer(str(svg_path))
            if not renderer.isValid():
                return None
            icon = QtGui.QIcon()
            for size in (16, 20, 24, 32, 48, 64):
                pm = QtGui.QPixmap(size, size)
                pm.fill(Qt.transparent)
                painter = QtGui.QPainter(pm)
                renderer.render(painter)
                painter.end()
                icon.addPixmap(pm)
            return icon if not icon.isNull() else None
        except Exception:
            return None

    def _refresh(self) -> None:
        """Repopulate the persistent menu with fresh state (called on open)."""
        from ..menu_model import build_menu
        from ..state import gather
        try:
            items = build_menu(gather(), self._update_state)
        except Exception:
            from ...applog import log_exception
            log_exception("tray/_refresh")
            return
        self._menu.clear()
        self._fill(self._menu, items)

    # -- auto-update --
    def _start_update_check(self) -> None:
        import threading
        from ..menu_model import UpdateMenuState
        self._update_state = UpdateMenuState(checking=True)

        def _work():
            info = None
            try:
                from ...update import service
                info = service.check_for_update()
            except Exception:
                from ...applog import log_exception
                log_exception("update/check")
            self._update_bridge.result.emit(info)

        threading.Thread(target=_work, daemon=True).start()

    def _on_update_result(self, info) -> None:
        """GUI thread: store result, notify, and auto-apply if opted in."""
        from ..menu_model import UpdateMenuState
        self._update_info = info
        self._update_state = UpdateMenuState(
            available_version=info.version if info is not None else None)
        if info is None:
            return
        try:
            from ...config import load_update_config
            if load_update_config().auto_apply:
                self._route("apply_update")
                return
            if self._tray is not None:
                self._tray.showMessage("Daimon", f"Update available: v{info.version}")
        except Exception:
            from ...applog import log_exception
            log_exception("update/notify")

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
        elif action_id == "check_update":
            self._start_update_check()
        elif action_id == "apply_update":
            if self._update_info is not None:
                from ...update import service
                service.apply_update(self._update_info)  # spawns the detached updater
                if self._app is not None:
                    self._app.quit()                     # release file locks for the replace
        elif action_id == "quit":
            if self._app is not None:
                self._app.quit()

    def _open_folder(self, which: str) -> None:
        import os
        from ...userdata import config_dir, logs_dir
        d = config_dir() if which == "config" else logs_dir()
        d.mkdir(parents=True, exist_ok=True)
        os.startfile(str(d))  # noqa: S606 — open the folder in Explorer


# Held for the tray process's lifetime so only one Daimon tray runs at a time.
# Without it, every relaunch (double-click, installer "launch on finish", a
# stale build never quit) leaves another resident tray — stacking duplicate
# icons and stale menus (an old v0.0.3 tray was found lingering this way).
_tray_lock_fd = None


def _acquire_singleton() -> bool:
    """Exclusive file lock so a second Daimon tray exits instead of stacking."""
    global _tray_lock_fd
    import os
    try:
        import msvcrt
        from ...userdata import data_dir
        d = data_dir()
        d.mkdir(parents=True, exist_ok=True)
        fd = os.open(str(d / "tray.lock"), os.O_CREAT | os.O_RDWR)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError:
            os.close(fd)
            return False  # another tray already holds it
        _tray_lock_fd = fd  # hold for the life of the process
        return True
    except Exception:
        return True  # never block the tray on a lock-mechanism failure


def main() -> int:
    from PySide6 import QtWidgets

    if not _acquire_singleton():
        return 0  # another Daimon tray is already resident

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    app.setQuitOnLastWindowClosed(False)  # resident tray app, no main window
    controller = WindowsTrayController()
    controller.install(app)
    app.exec()
    return 0
