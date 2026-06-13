"""macOS permission status + guidance. We never *grant* TCC (impossible by
design); we detect, trigger the system prompt, open the right Settings pane, and
verify. Calls are behind a backend so the model is testable without macOS."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

PANE_SCREEN = "x-apple.systempreferences:com.apple.preference.security?Privacy_ScreenCapture"
PANE_ACCESSIBILITY = "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"


@dataclass(frozen=True)
class Permission:
    key: str
    label: str
    granted: bool
    pane: str
    how_to: str


class PermissionBackend(Protocol):
    def screen_recording_ok(self) -> bool: ...
    def accessibility_ok(self) -> bool: ...
    def request_screen_recording(self) -> None: ...
    def request_accessibility(self) -> None: ...
    def open_pane(self, pane: str) -> None: ...


class FakeBackend:
    def __init__(self, screen=False, accessibility=False):
        self._screen = screen
        self._acc = accessibility
        self.requested: list[str] = []
        self.opened: list[str] = []
    def screen_recording_ok(self): return self._screen
    def accessibility_ok(self): return self._acc
    def request_screen_recording(self): self.requested.append("screen")
    def request_accessibility(self): self.requested.append("accessibility")
    def open_pane(self, pane): self.opened.append(pane)


class MacOSBackend:
    def screen_recording_ok(self) -> bool:
        from Quartz import CGPreflightScreenCaptureAccess
        return bool(CGPreflightScreenCaptureAccess())
    def accessibility_ok(self) -> bool:
        from ApplicationServices import AXIsProcessTrusted
        return bool(AXIsProcessTrusted())
    def request_screen_recording(self) -> None:
        from Quartz import CGRequestScreenCaptureAccess
        CGRequestScreenCaptureAccess()
    def request_accessibility(self) -> None:
        from ApplicationServices import AXIsProcessTrustedWithOptions
        AXIsProcessTrustedWithOptions({"AXTrustedCheckOptionPrompt": True})
    def open_pane(self, pane: str) -> None:
        import subprocess
        subprocess.run(["open", pane], check=False)


def permissions_status(backend: PermissionBackend) -> list[Permission]:
    return [
        Permission("screen_recording", "Screen Recording (Vue)", backend.screen_recording_ok(),
                   PANE_SCREEN, "Lets Daimon see your screen."),
        Permission("accessibility", "Accessibility (Touché + Hands)", backend.accessibility_ok(),
                   PANE_ACCESSIBILITY, "Lets Daimon read UI structure and act."),
    ]
