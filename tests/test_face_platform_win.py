"""WindowsFaceAdapter — the Win32 native window traits degrade safely.

The adapter is pure ctypes; every method must no-op (never raise) when the HWND
isn't available yet — pywebview sets `window.native` only once the GUI loop has
created the window. Windows-only: the module imports `ctypes.wintypes`, which is
not guaranteed importable off Windows, so both the import and the tests are
gated here (and done lazily inside the tests, not at collection)."""

from __future__ import annotations

import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows-only face adapter")


class _NoNative:
    native = None


def test_adapter_methods_noop_without_native_handle():
    from daimon.face.platform.windows import WindowsFaceAdapter

    a = WindowsFaceAdapter()
    w = _NoNative()
    # None of these may raise when the HWND isn't ready.
    a.run_on_main(lambda: None)
    a.apply_vibrancy(w, dark=True, radius=20)
    a.exclude_from_capture(w)
    a.set_click_through(w)
    a.fit_to_screen(w)
    a.anchor_under_statusitem(w, None)
    assert a.watch_outside_click(w, None, lambda: None) is None


def test_run_on_main_calls_through():
    from daimon.face.platform.windows import WindowsFaceAdapter

    seen = []
    WindowsFaceAdapter().run_on_main(lambda: seen.append(1))
    assert seen == [1]


def test_hwnd_none_when_native_absent():
    from daimon.face.platform.windows import _hwnd

    assert _hwnd(_NoNative()) is None
    assert _hwnd(object()) is None
