"""NSStatusItem controller — renders the menu-bar icon and the dropdown menu.

All AppKit / ObjC imports are deferred inside methods so that bare import works
on any platform (Linux, Windows, CI without pyobjc installed).

Menu structure comes from ``daimon.tray.menu_model.build_menu`` (pure,
unit-tested).  ``StatusItemController.install()`` does the AppKit wiring.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..menu_model import MenuItem


# ---------------------------------------------------------------------------
# StatusItemController
# ---------------------------------------------------------------------------

class StatusItemController:
    """Manages a single NSStatusItem in the macOS system menu bar.

    Call ``install()`` once after the NSApplication is set up.  All subsequent
    state refreshes happen via a ~2 s poll driven by PyObjCTools.AppHelper.
    """

    def __init__(self) -> None:
        self._status_item = None
        self._menu = None
        # Keep references to ObjC targets so they are not GC'd.
        self._targets: list = []
        # Keep a reference to any open onboarding controller.
        self._onboard = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def install(self) -> None:
        """Create the NSStatusItem and start the poll loop."""
        from AppKit import NSStatusBar
        from PyObjCTools import AppHelper

        bar = NSStatusBar.systemStatusBar()
        # -1 == NSVariableStatusItemLength
        self._status_item = bar.statusItemWithLength_(-1)
        btn = self._status_item.button()
        if btn is not None:
            btn.setTitle_("δ")

        self._rebuild_menu()
        AppHelper.callLater(2.0, self._poll)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _poll(self) -> None:
        """Rebuild the menu with fresh state, then schedule the next poll."""
        from PyObjCTools import AppHelper
        try:
            self._rebuild_menu()
        except Exception:
            from daimon.applog import log_exception
            log_exception("poll/_rebuild_menu")
        AppHelper.callLater(2.0, self._poll)

    def _rebuild_menu(self) -> None:
        """Read the current tray state and re-render the NSMenu."""
        from AppKit import NSMenu

        from ..menu_model import build_menu
        from ..state import gather

        state = gather()
        items = build_menu(state)

        menu = NSMenu.alloc().init()
        menu.setAutoenablesItems_(False)
        self._targets = []  # release old targets
        self._fill_menu(menu, items)

        self._status_item.setMenu_(menu)
        self._menu = menu

    def _fill_menu(self, ns_menu, items: list[MenuItem]) -> None:
        """Recursively populate *ns_menu* from a list of ``MenuItem`` objects."""
        from AppKit import NSMenuItem

        for item in items:
            ns_item = self._make_ns_item(item)
            ns_menu.addItem_(ns_item)

    def _make_ns_item(self, item: MenuItem):
        """Convert a ``MenuItem`` to an ``NSMenuItem``."""
        from AppKit import NSMenu, NSMenuItem

        kind = item.kind

        if kind == "separator":
            return NSMenuItem.separatorItem()

        ns_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            item.label, None, ""
        )

        if kind == "label":
            ns_item.setEnabled_(False)
            return ns_item

        if kind == "submenu":
            submenu = NSMenu.alloc().initWithTitle_(item.label)
            submenu.setAutoenablesItems_(False)
            self._fill_menu(submenu, list(item.children))
            ns_item.setSubmenu_(submenu)
            ns_item.setEnabled_(True)
            return ns_item

        # action / radio / checkbox — wire a target
        from ...objc_bridge import make_target
        action_id = item.action_id
        callback = self._make_callback(action_id)
        target = make_target(callback)
        self._targets.append(target)

        ns_item.setTarget_(target)
        ns_item.setAction_("invoke:")
        ns_item.setEnabled_(item.enabled)

        if kind == "checkbox" or kind == "radio":
            # NSMenuItem state: 1 = on (checkmark), 0 = off
            ns_item.setState_(1 if item.checked else 0)

        return ns_item

    def _make_callback(self, action_id: str):
        """Return a zero-argument callable for *action_id*."""

        def callback():
            try:
                self._dispatch(action_id)
            except Exception:
                from ...applog import log_exception
                log_exception(action_id)

        return callback

    def _dispatch(self, action_id: str) -> None:
        """Route *action_id* to the appropriate handler."""
        if action_id.startswith("set_ceiling:"):
            name = action_id[len("set_ceiling:"):]
            from ..settings import set_ceiling
            from ...config import _MOTOR_DEFAULT
            set_ceiling(name, _MOTOR_DEFAULT)
            self._rebuild_menu()

        elif action_id == "toggle_overlay":
            from ..state import gather
            from ..settings import set_overlay
            from ...config import _OVERLAY_DEFAULT
            current = gather().overlay_on
            set_overlay(not current, _OVERLAY_DEFAULT)
            self._rebuild_menu()

        elif action_id == "install_all":
            from ...applog import log_exception
            try:
                from ...setup.deploy import install_all
                install_all()
                self._rebuild_menu()
            except Exception:
                log_exception("install_all")

        elif action_id.startswith("toggle_client:"):
            from ...applog import log_exception
            name = action_id[len("toggle_client:"):]
            try:
                from ...setup.clients import base
                from ...setup.clients.registry import default_adapters, detected
                from ...setup.invocation import daimon_command
                adapter = next((a for a in detected(default_adapters()) if a.name == name), None)
                if adapter is not None:
                    if base.status(adapter, "daimon").action == "present":
                        base.uninstall(adapter, "daimon")
                    else:
                        base.install(adapter, "daimon", daimon_command())
                self._rebuild_menu()
            except Exception:
                log_exception("toggle_client")

        elif action_id == "run_setup":
            from ...applog import log_exception, log_message
            log_message("run_setup: opening onboarding window")
            try:
                from ...setup.gui.window import OnboardingController
                from ...setup.permissions import MacOSBackend
                self._onboard = OnboardingController(MacOSBackend())
                self._onboard.show()
                log_message("run_setup: onboarding window shown")
            except Exception:
                log_exception("run_setup")

        elif action_id == "open_config":
            try:
                import subprocess
                from ...userdata import config_dir
                d = config_dir()
                d.mkdir(parents=True, exist_ok=True)
                subprocess.run(["open", str(d)], check=False)
            except Exception:
                from ...applog import log_exception
                log_exception(action_id)

        elif action_id == "open_logs":
            try:
                import subprocess
                from ...userdata import logs_dir
                d = logs_dir()
                d.mkdir(parents=True, exist_ok=True)
                subprocess.run(["open", str(d)], check=False)
            except Exception:
                from ...applog import log_exception
                log_exception(action_id)

        elif action_id == "quit":
            from AppKit import NSApp
            NSApp.terminate_(None)
