"""The cooperative test session: durable, ledgered pre-authorization for pacte_act."""

from __future__ import annotations

from typing import Callable

from ..motor.audit import AppendOnlyLedger
from ..motor.types import Level

DEFAULT_SESSION_CEILING = Level.VALIDATION


class CooperativeSession:
    """Active flag + ceiling for a cooperative drive session, recorded immutably."""

    def __init__(self, ledger: AppendOnlyLedger, clock: Callable[[], str],
                 ceiling: Level = DEFAULT_SESSION_CEILING) -> None:
        self._ledger = ledger
        self._clock = clock
        self._ceiling = min(ceiling, Level.VALIDATION)
        self._active = False

    def open(self, app: str, pid: int) -> None:
        """Begin a session: one ledger entry pre-authorizes acts up to the session ceiling."""
        self._ledger.append({"event": "cooperative_open", "ts": self._clock(),
                             "app": app, "pid": pid, "ceiling": self._ceiling.name})
        self._active = True

    def close(self) -> None:
        """End the session; record it. Acts refuse again until the next open()."""
        self._ledger.append({"event": "cooperative_close", "ts": self._clock()})
        self._active = False

    def active(self) -> bool:
        return self._active

    def ceiling(self) -> Level:
        return self._ceiling if self._active else Level.READ
