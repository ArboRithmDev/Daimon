"""macOS permission status + guidance. We never *grant* TCC (impossible by
design); we detect, trigger the system prompt, open the right Settings pane, and
verify. Calls are behind a backend so the model is testable without macOS."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
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


# -- self-report marker -----------------------------------------------------
# TCC permissions attach to the responsible parent GUI (the AI client that
# launches `daimon`), not to Daimon.app. So the onboarding GUI cannot verify
# the client's grant from its own process. Instead the server records its OWN
# (correct-context) permission status to a marker file on startup; the
# onboarding GUI reads it to confirm "your AI has the permissions".


def status_marker_path() -> Path:
    from ..userdata import data_dir
    return data_dir() / "permissions.json"


def record_status(backend: PermissionBackend, path: Path | None = None) -> dict:
    """Write the current (this-process-context) grant status. Best-effort."""
    path = path or status_marker_path()
    data = {p.key: p.granted for p in permissions_status(backend)}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data), encoding="utf-8")
    except OSError:
        pass
    return data


def read_status(path: Path | None = None) -> dict:
    """Read the last recorded grant status; {} if absent/unreadable."""
    path = path or status_marker_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}
