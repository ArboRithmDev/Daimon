"""Execute an authorized MotorAction by forwarding it over the cooperative channel."""

from __future__ import annotations

from ..motor.types import MotorAction
from .client import CooperativeClient


class CooperativeActuator:
    """The MotorOrgan actuator slot, backed by the JSON-RPC channel instead of the OS."""

    def __init__(self, client: CooperativeClient) -> None:
        self._client = client

    def execute(self, action: MotorAction) -> dict:
        """Forward the verb + args to the endpoint's `act` method; return its result."""
        return self._client.call("act", {"verb": action.name, "args": action.params.get("args", {})})
