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
    """

    def __init__(self, state: FocusState | None = None, *, activates: bool = False) -> None:
        self._state = state
        self._activates = activates
        self.activated: list[dict] = []

    def frontmost(self) -> FocusState | None:
        return self._state

    def note_activated(self, window: dict) -> None:
        """Called by the organ after it issues an activate, so the fake can flip."""
        self.activated.append(window)
        if self._activates:
            self._state = FocusState(
                bundle=window.get("bundle"),
                title=window.get("title"),
                pid=window.get("pid"),
            )


class MacOSFocusProbe:
    """Real backend: reads the frontmost app via NSWorkspace."""

    def frontmost(self) -> FocusState | None:
        from AppKit import NSWorkspace

        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        if app is None:
            return None
        return FocusState(
            bundle=app.bundleIdentifier(),
            title=app.localizedName(),
            pid=int(app.processIdentifier()),
        )


class WindowsFocusProbe:
    """Parity scaffold: read the foreground window's app on Windows.

    TODO(windows): implement with GetForegroundWindow + GetWindowThreadProcessId
    to obtain the pid, then resolve the process image name / window title. The
    seam (FocusProbe protocol + FocusState) and the OS-agnostic matcher
    (window_is_frontmost) are already shared with the macOS twin, so wiring this
    closes F3 on Windows without touching the organ.
    """

    def frontmost(self) -> FocusState | None:  # pragma: no cover - Windows runtime
        raise NotImplementedError(
            "WindowsFocusProbe.frontmost requires the Win32 runtime "
            "(GetForegroundWindow / GetWindowThreadProcessId)."
        )
