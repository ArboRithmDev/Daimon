"""TrayActions — the real ActionHandlers, shared by the AppKit menu and the
webview face. Pure effects live here; the few host-specific bits (the L4 consent
confirmation, opening onboarding, quitting the app, refreshing the UI) are
injected callbacks so the same handlers serve both renderers.

The settings/deploy/consent effects are thin wrappers over already-tested modules
and are exercised by the live app; the injected-callback wiring (L4 gating,
quit/run_setup delegation) is unit-tested."""

from __future__ import annotations

from typing import Callable


def _utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


class TrayActions:
    """Concrete ActionHandlers. `confirm_l4` MUST return True before L4 engages
    (defaults to refusing, so L4 never engages without an explicit host dialog)."""

    def __init__(
        self,
        *,
        on_change: Callable[[], None] = lambda: None,
        confirm_l4: Callable[[], bool] = lambda: False,
        open_onboarding: Callable[[], None] = lambda: None,
        on_quit: Callable[[], None] = lambda: None,
    ) -> None:
        self._changed = on_change
        self._confirm_l4 = confirm_l4
        self._open_onboarding = open_onboarding
        self._quit = on_quit

    def set_ceiling(self, name: str) -> None:
        from .settings import set_ceiling
        from ..config import _MOTOR_DEFAULT
        set_ceiling(name, _MOTOR_DEFAULT)
        self._changed()

    def toggle_overlay(self) -> None:
        from .state import gather
        from .settings import set_overlay
        from ..config import _OVERLAY_DEFAULT
        set_overlay(not gather().overlay_on, _OVERLAY_DEFAULT)
        self._changed()

    def install_all(self) -> None:
        from ..applog import log_exception
        try:
            from ..setup.deploy import install_all
            install_all()
            self._changed()
        except Exception:
            log_exception("install_all")

    def toggle_client(self, name: str) -> None:
        from ..applog import log_exception
        try:
            from ..setup.clients import base
            from ..setup.clients.registry import default_adapters, detected
            from ..setup.invocation import daimon_command
            adapter = next((a for a in detected(default_adapters()) if a.name == name), None)
            if adapter is not None:
                if base.status(adapter, "daimon").action == "present":
                    base.uninstall(adapter, "daimon")
                else:
                    base.install(adapter, "daimon", daimon_command())
            self._changed()
        except Exception:
            log_exception("toggle_client")

    def engage_l4(self) -> None:
        from ..applog import log_exception
        try:
            if not self._confirm_l4():
                return
            from ..motor.factory import build_consent
            build_consent().engage_confirmed(ts=_utc_now(), source="tray")
            self._changed()
        except Exception:
            log_exception("engage_l4")

    def disengage_l4(self) -> None:
        from ..applog import log_exception
        try:
            from ..motor.factory import build_consent
            build_consent().disengage_confirmed(ts=_utc_now(), source="tray")
            self._changed()
        except Exception:
            log_exception("disengage_l4")

    def run_setup(self) -> None:
        self._open_onboarding()

    def open_config(self) -> None:
        from ..applog import log_exception
        try:
            import subprocess
            from ..userdata import config_dir
            d = config_dir()
            d.mkdir(parents=True, exist_ok=True)
            subprocess.run(["open", str(d)], check=False)
        except Exception:
            log_exception("open_config")

    def open_logs(self) -> None:
        from ..applog import log_exception
        try:
            import subprocess
            from ..userdata import logs_dir
            d = logs_dir()
            d.mkdir(parents=True, exist_ok=True)
            subprocess.run(["open", str(d)], check=False)
        except Exception:
            log_exception("open_logs")

    def quit(self) -> None:
        self._quit()

    # --- Onboarding permission gestures -------------------------------------

    def grant_screen(self) -> None:
        from ..setup.permissions import MacOSBackend
        MacOSBackend().request_screen_recording()
        self._changed()

    def grant_accessibility(self) -> None:
        from ..setup.permissions import MacOSBackend
        MacOSBackend().request_accessibility()
        self._changed()

    def settings_screen(self) -> None:
        from ..setup.permissions import MacOSBackend, PANE_SCREEN
        MacOSBackend().open_pane(PANE_SCREEN)

    def settings_accessibility(self) -> None:
        from ..setup.permissions import MacOSBackend, PANE_ACCESSIBILITY
        MacOSBackend().open_pane(PANE_ACCESSIBILITY)
