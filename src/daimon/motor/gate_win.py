"""Out-of-band human confirmation for points of no return, on Windows.

The Windows twin of ``MacOSGate``. The threat it closes: on Windows a process
at the same integrity level can ``SendInput`` to any window at its level — so a
plain confirmation dialog could be *self-confirmed* by the very agent it gates.

Defence: the dialog is shown on a **separate desktop** (``CreateDesktop`` +
``SwitchDesktop``), the same isolation mechanism UAC uses. Synthetic input from
the agent runs on the Default desktop and cannot reach a window on the Daimon
gate desktop, so the agent cannot click "Yes" for the human. The original
desktop is always restored, and any timeout or error resolves to DENY
(fail-safe parity with macOS).

Seams (``dialog`` / ``switcher``) are injectable so the confirm-decision logic
is unit-tested without ever blanking the screen; the real desktop switch is
exercised only by an opt-in interactive smoke.
"""

from __future__ import annotations

import ctypes
import threading
from ctypes import wintypes
from typing import Callable, Protocol

from .gate import format_prompt  # reuse the pure, unit-tested prompt
from .types import MotorAction

_TIMEOUT_SECONDS = 30
_TITLE = "Daimon — Confirmation"

# MessageBox flags / return codes.
_MB_YESNO = 0x00000004
_MB_ICONWARNING = 0x00000030
_MB_DEFBUTTON2 = 0x00000100      # default = No (fail-safe)
_MB_SYSTEMMODAL = 0x00001000
_MB_SETFOREGROUND = 0x00010000
_MB_TOPMOST = 0x00040000
_IDYES = 6
_MB_TIMEDOUT = 32000

# Desktop access right used for create/switch.
_GENERIC_ALL = 0x10000000

_user32 = ctypes.WinDLL("user32", use_last_error=True)


# --- low-level dialog on a desktop -----------------------------------------

def _message_box_timeout(prompt: str, timeout_ms: int) -> int:
    """MessageBoxTimeoutW — a Yes/No box that auto-dismisses after a timeout."""
    fn = _user32.MessageBoxTimeoutW
    fn.restype = ctypes.c_int
    flags = (_MB_YESNO | _MB_ICONWARNING | _MB_DEFBUTTON2
             | _MB_SYSTEMMODAL | _MB_SETFOREGROUND | _MB_TOPMOST)
    return fn(None, ctypes.c_wchar_p(prompt), ctypes.c_wchar_p(_TITLE),
              wintypes.UINT(flags), wintypes.WORD(0), wintypes.DWORD(timeout_ms))


def _confirm_on_secure_desktop(prompt: str, timeout: int,
                               dialog: Callable[[str, int], int]) -> bool:
    """Create + switch to an isolated desktop, run ``dialog`` there, restore.

    Returns True only on an explicit Yes. Any failure path restores the original
    input desktop and returns False.
    """
    orig = _user32.OpenInputDesktop(0, False, _GENERIC_ALL)
    new = _user32.CreateDesktopW(
        ctypes.c_wchar_p("DaimonGate"), None, None, 0, _GENERIC_ALL, None)
    if not new:
        if orig:
            _user32.CloseDesktop(orig)
        return False

    result = {"code": _MB_TIMEDOUT}

    def _run():
        # Bind THIS thread to the gate desktop before creating any window.
        _user32.SetThreadDesktop(new)
        try:
            result["code"] = dialog(prompt, timeout * 1000)
        except Exception:
            result["code"] = _MB_TIMEDOUT

    try:
        _user32.SwitchDesktop(new)
        t = threading.Thread(target=_run, daemon=True)
        t.start()
        t.join(timeout + 5)
        return result["code"] == _IDYES
    except Exception:
        return False
    finally:
        if orig:
            try:
                _user32.SwitchDesktop(orig)
            except Exception:
                pass
            _user32.CloseDesktop(orig)
        _user32.CloseDesktop(new)


# --- gate -------------------------------------------------------------------

class HumanGate(Protocol):
    def confirm(self, action: MotorAction) -> bool: ...


class WindowsGate:
    """Native confirmation on an isolated desktop. Timeout/error → DENY.

    ``confirmer`` lets tests inject the secure-desktop step so confirm() logic is
    verified without switching desktops; the default runs the real switch.
    """

    def __init__(self, confirmer: Callable[[str, int], bool] | None = None) -> None:
        self._confirmer = confirmer or (
            lambda prompt, timeout: _confirm_on_secure_desktop(
                prompt, timeout, _message_box_timeout))

    def confirm(self, action: MotorAction) -> bool:
        try:
            return bool(self._confirmer(format_prompt(action), _TIMEOUT_SECONDS))
        except Exception:
            return False
