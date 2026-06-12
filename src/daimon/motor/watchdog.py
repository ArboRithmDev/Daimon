"""Auto-release safety net for held inputs (primitives).

A low-level mouse_down/key_down may never get its up if the agent errors. The
watchdog tracks holds with a deadline; tick() releases any past-deadline hold.
Pure — the actuator injects the real release fn and clock."""

from __future__ import annotations

from typing import Callable


class HoldWatchdog:
    def __init__(self, timeout: float, release: Callable[[str], None], clock: Callable[[], float]):
        self._timeout = timeout
        self._release = release
        self._clock = clock
        self._held: dict[str, float] = {}

    def hold(self, handle: str) -> None:
        self._held[handle] = self._clock() + self._timeout

    def release_hold(self, handle: str) -> None:
        self._held.pop(handle, None)

    def tick(self) -> None:
        now = self._clock()
        for handle in [h for h, deadline in self._held.items() if now >= deadline]:
            self._held.pop(handle, None)
            self._release(handle)

    def active(self) -> set[str]:
        return set(self._held)
