"""Platform backend selector.

Resolves the OS-specific implementations behind builder functions so the pure
core (factory, organ, senses, setup) never imports a platform module directly.
Dispatch is on ``sys.platform``: the macOS path returns the existing
pyobjc-backed classes; the Windows path is filled in by later phases of the
Windows port (W1–W4). Platform implementations are imported **lazily** inside
each builder, so importing this module is safe on any OS.

Consumption map:
  - build_actuator / build_gate / build_prober   → motor/factory.py (wired in W0)
  - build_screen / build_a11y                    → senses (wired in W1)
  - build_permissions_backend                    → setup (wired in W4)
"""

from __future__ import annotations

import sys

# Marker for not-yet-ported Windows backends. Each builder names the phase that
# lands it, so a premature call on Windows fails loudly rather than silently.
_WIN_PENDING = "Windows backend not implemented yet"


def _unsupported() -> "NotImplementedError":
    return NotImplementedError(f"unsupported platform: {sys.platform}")


# --- Motor (wired in W0) ---------------------------------------------------

def build_actuator():
    """Physical actuator (the hands)."""
    if sys.platform == "darwin":
        from ..motor.actuator import MacOSActuator
        return MacOSActuator()
    if sys.platform == "win32":
        from ..motor.actuator_win import WindowsActuator
        return WindowsActuator()
    raise _unsupported()


def build_gate():
    """Out-of-band human confirmation gate for points of no return."""
    if sys.platform == "darwin":
        from ..motor.gate import MacOSGate
        return MacOSGate()
    if sys.platform == "win32":
        from ..motor.gate_win import WindowsGate
        return WindowsGate()
    raise _unsupported()


def build_prober():
    """Re-observe the actual target via the platform accessibility API."""
    if sys.platform == "darwin":
        from ..motor.probe import MacOSProber
        return MacOSProber()
    if sys.platform == "win32":
        from ..motor.prober_win import WindowsProber
        return WindowsProber()
    raise _unsupported()


# --- Senses (wired in W1) --------------------------------------------------

def build_screen():
    """Screen-capture backend module for the Vue sense."""
    if sys.platform == "darwin":
        from ..capture import screen
        return screen
    if sys.platform == "win32":
        from ..capture import screen_win
        return screen_win
    raise _unsupported()


def build_a11y():
    """Accessibility backend module for the Touché sense."""
    if sys.platform == "darwin":
        from ..capture import accessibility
        return accessibility
    if sys.platform == "win32":
        from ..capture import accessibility_win
        return accessibility_win
    raise _unsupported()


# --- Permissions (wired in W4) ---------------------------------------------

def build_permissions_backend():
    """OS permission status backend (TCC on macOS; no-op + UIPI on Windows)."""
    if sys.platform == "darwin":
        from ..setup.permissions import MacOSBackend
        return MacOSBackend()
    if sys.platform == "win32":
        raise NotImplementedError(f"{_WIN_PENDING}: permissions (W4)")
    raise _unsupported()
