"""Focus awareness for positional Hands (F3).

A click aimed at a window that is not frontmost is a silent no-op on the host:
the OS routes synthetic mouse events to whatever is actually frontmost, so the
gesture is *emitted* but has no *observable effect*. Nothing in the result tells
the client these two apart, and the pilot mistakes it for a coordinate error.

This module is the pure seam that makes focus observable. `FocusState` is the
frontmost app identity; `window_is_frontmost` is the OS-agnostic matcher the
organ uses to decide whether to auto-activate (`ensure_focus`) or to attach an
explicit focus warning. Each backend ships a `Fake*` so the core is tested
without the OS, and both platforms carry a twin (macOS real, Windows scaffold).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class FocusState:
    """Identity of the frontmost application, for comparison with a target window."""

    bundle: str | None = None
    title: str | None = None
    pid: int | None = None


def window_is_frontmost(state: FocusState | None, window: dict | None) -> bool | None:
    """Whether `window` matches the frontmost app.

    Returns None when there is nothing to judge (no target window declared) so
    the caller can stay silent; True/False only when a window was specified.
    A window matches if any declared key (bundle/title/pid) equals the state's.
    Unknown focus (`state is None`) with a declared window is False — we cannot
    confirm the target is frontmost, so we must warn rather than assume.
    """
    if not window:
        return None
    if state is None:
        return False
    if window.get("bundle") is not None and window["bundle"] == state.bundle:
        return True
    if window.get("title") is not None and window["title"] == state.title:
        return True
    if window.get("pid") is not None and int(window["pid"]) == (state.pid or -1):
        return True
    return False


class FocusProbe(Protocol):
    """Reports which application is frontmost; swappable for testing."""

    def frontmost(self) -> FocusState | None: ...


class FakeFocusProbe:
    """Test double: returns a preset frontmost state.

    With `activates=True` it models the real activation effect — after the organ
    issues an activate, the next `frontmost()` reports the activated window,
    letting tests assert the organ observes the focus change.

    With `activates_after_polls=k` it models *asynchronous* activation: the
    switch is only visible after `k` further `frontmost()` polls, so a single
    immediate re-check still sees the old frontmost. This exercises the organ's
    bounded settle/retry after an activate (it must not report a false negative
    just because the window server had not switched yet).
    """

    def __init__(self, state: FocusState | None = None, *, activates: bool = False,
                 activates_after_polls: int = 0) -> None:
        self._state = state
        self._activates = activates or activates_after_polls > 0
        self._activates_after_polls = activates_after_polls
        self._pending: FocusState | None = None
        self._polls_left = 0
        self.activated: list[dict] = []

    def frontmost(self) -> FocusState | None:
        if self._pending is not None:
            if self._polls_left <= 0:
                self._state = self._pending
                self._pending = None
            else:
                self._polls_left -= 1
        return self._state

    def note_activated(self, window: dict) -> None:
        """Called by the organ after it issues an activate, so the fake can flip."""
        self.activated.append(window)
        if not self._activates:
            return
        switched = FocusState(
            bundle=window.get("bundle"),
            title=window.get("title"),
            pid=window.get("pid"),
        )
        if self._activates_after_polls > 0:
            self._pending = switched
            self._polls_left = self._activates_after_polls
        else:
            self._state = switched


class MacOSFocusProbe:
    """Real backend: reads the frontmost app from the window server.

    Deliberately NOT `NSWorkspace.frontmostApplication()`: that value is updated
    by an AppKit notification delivered on the main run loop, so it never
    refreshes while the motor organ blocks (time.sleep) waiting for an activation
    to settle — the re-check polls a stale value forever and a successful
    activation is misreported as "still not frontmost". The window server's
    on-screen list reflects the real frontmost window within tens of ms, with no
    run-loop dependency, so it matches what a synthetic click will actually hit.
    """

    def frontmost(self) -> FocusState | None:
        from AppKit import NSRunningApplication
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGWindowListOptionOnScreenOnly,
            kCGWindowLayer,
            kCGWindowOwnerPID,
        )

        infos = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, 0) or []
        # The list is front-to-back; the first normal-app window (layer 0) belongs
        # to the frontmost application (menu bar / system UI sit on other layers).
        pid = None
        for win in infos:
            if win.get(kCGWindowLayer) == 0:
                pid = win.get(kCGWindowOwnerPID)
                break
        if pid is None:
            return None
        app = NSRunningApplication.runningApplicationWithProcessIdentifier_(int(pid))
        if app is None:
            return FocusState(pid=int(pid))
        return FocusState(
            bundle=app.bundleIdentifier(),
            title=app.localizedName(),
            pid=int(pid),
        )


class WindowsFocusProbe:
    """Real backend: read the foreground window's app on Windows.

    GetForegroundWindow returns the live foreground window with no run-loop
    dependency (the Windows twin of the macOS window-server probe — and for the
    same reason: it reflects what a synthetic click will actually hit). The pid
    comes from GetWindowThreadProcessId; `bundle` is the process image path (the
    Windows analogue of a macOS bundle id, matching screen_win.frontmost_bundle_id),
    `title` is the window text. The OS-agnostic matcher (window_is_frontmost) and
    the organ are unchanged.
    """

    def frontmost(self) -> FocusState | None:  # pragma: no cover - Windows runtime
        import win32gui
        import win32process

        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        title = win32gui.GetWindowText(hwnd) or None
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
        except Exception:
            return FocusState(title=title)
        if not pid:
            return FocusState(title=title)

        image = None
        try:
            import win32api
            import win32con
            h = win32api.OpenProcess(
                win32con.PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
            try:
                image = win32process.GetModuleFileNameEx(h, 0)
            finally:
                win32api.CloseHandle(h)
        except Exception:
            pass

        return FocusState(bundle=image, title=title, pid=int(pid))
