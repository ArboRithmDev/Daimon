"""No-op adapter for platforms without native window traits (e.g. Linux today).
Keeps the host code branch-free; the surfaces still render, just without
vibrancy / anchoring / capture-exclusion."""

from __future__ import annotations


class NoopFaceAdapter:
    def apply_vibrancy(self, window, *, dark: bool = True, radius: int = 20) -> None:
        pass

    def exclude_from_capture(self, window) -> None:
        pass

    def set_click_through(self, window) -> None:
        pass

    def fit_to_screen(self, window) -> None:
        pass

    def anchor_under_statusitem(self, window, statusitem) -> None:
        pass
