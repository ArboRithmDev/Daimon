"""Windows host gestures for the face panel — the Win32 twins of native.py.

pywebview invokes bridge methods on a worker thread; a Win32 MessageBox is
thread-safe, so the L4 confirmation runs inline. Onboarding is the existing
setup GUI, spawned as its own process (the panel keeps its own webview loop)."""

from __future__ import annotations

import subprocess
import sys

_MB_OKCANCEL = 0x00000001
_MB_ICONWARNING = 0x00000030
_MB_TOPMOST = 0x00040000
_IDOK = 1


def confirm_l4() -> bool:
    """Show the L4 consent disclaimer and return True only on OK. Fail-closed:
    any error (no user32, headless) returns False — autonomy never auto-engages."""
    try:
        import ctypes

        res = ctypes.windll.user32.MessageBoxW(
            0,
            "Removes ALL per-action validation. Every action the AI requests will "
            "execute immediately, recorded in the immutable consent ledger. "
            "Disengage anytime from the tray.",
            "Engage L4 autonomy?",
            _MB_OKCANCEL | _MB_ICONWARNING | _MB_TOPMOST,
        )
        return res == _IDOK
    except Exception:
        return False


def _gui_cmd() -> list[str]:
    # Frozen: sys.executable is Daimon.exe — dispatch on the `--gui` flag. From
    # source: go through `-m daimon --gui`.
    if getattr(sys, "frozen", False):
        return [sys.executable, "--gui"]
    return [sys.executable, "-m", "daimon", "--gui"]


def open_onboarding() -> None:
    """Open the Windows setup/onboarding GUI as its own process. Best-effort."""
    try:
        subprocess.Popen(_gui_cmd(), stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, close_fds=True)
    except Exception:
        pass
