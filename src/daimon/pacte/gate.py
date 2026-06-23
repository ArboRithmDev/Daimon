"""The gate MotorOrgan calls for cooperative acts: satisfied by the durable session consent."""

from __future__ import annotations

from ..motor.types import MotorAction
from .session import CooperativeSession


class CooperativeGate:
    """Confirms an act iff a session is open and the act is within the session ceiling."""

    def __init__(self, session: CooperativeSession) -> None:
        self._session = session

    def confirm(self, action: MotorAction) -> bool:
        """No live dialog: the open-session ledger entry is the standing consent."""
        return self._session.active() and action.level <= self._session.ceiling()
