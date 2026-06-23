"""Build a fully-wired Pacte organ from config + real per-platform pieces."""

from __future__ import annotations

from datetime import datetime, timezone

from ..config import load_config
from ..exclusions import ExclusionFilter
from ..motor.audit import AppendOnlyLedger
from ..motor.guard import PolicyGuard
from ..motor.organ import MotorOrgan
from ..motor.types import MotorAction, Target
from ..userdata import cooperative_dir, logs_dir
from .actuator import CooperativeActuator
from .client import CooperativeClient
from .gate import CooperativeGate
from .organ import Pacte
from .session import CooperativeSession


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class _PassThroughProber:
    """The cooperating endpoint is authoritative for the target; no OS observation here."""

    def observe(self, action: MotorAction) -> Target:
        return action.target


def build_pacte() -> Pacte:
    """Assemble the Pacte organ: discovery + redaction + session-gated motor chokepoint."""
    exclusions = ExclusionFilter(load_config().exclusions)
    logs = logs_dir()
    logs.mkdir(parents=True, exist_ok=True)
    ledger = AppendOnlyLedger(logs / "cooperative.jsonl")
    session = CooperativeSession(ledger, clock=_now)

    def motor_organ_factory(client: CooperativeClient) -> MotorOrgan:
        guard = PolicyGuard(exclusions, ceiling_provider=session.ceiling)
        return MotorOrgan(
            guard=guard, gate=CooperativeGate(session),
            actuator=CooperativeActuator(client),
            session_log=ledger, clock=_now, prober=_PassThroughProber(),
        )

    return Pacte(exclusions, session, motor_organ_factory, cooperative_dir=cooperative_dir())
