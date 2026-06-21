"""Per-OS native window traits for the face surfaces (vibrancy, anchor,
capture-exclusion). The face core is OS-agnostic; these adapters carry the
platform-specific AppKit/Win32 calls. Selected at runtime by `get_adapter()`."""

from __future__ import annotations

import sys


def get_adapter():
    """Return the native window adapter for the current OS."""
    if sys.platform == "darwin":
        from .macos import MacOSFaceAdapter
        return MacOSFaceAdapter()
    if sys.platform == "win32":
        from .windows import WindowsFaceAdapter
        return WindowsFaceAdapter()
    from .noop import NoopFaceAdapter
    return NoopFaceAdapter()
