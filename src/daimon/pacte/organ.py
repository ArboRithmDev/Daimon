"""Pacte — the cooperative channel organ. Generic: speaks the protocol, never imports Qt.

pacte_describe handshakes + opens a cooperative session; pacte_probe reads redacted state;
pacte_act runs each verb through the SAME MotorOrgan chokepoint (ceiling + ledger), satisfied
by the durable session consent rather than a per-action dialog.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from ..exclusions import ExclusionFilter
from ..motor.organ import MotorOrgan
from ..motor.types import Declaration, Level, MotorAction, Target
from .client import CooperativeClient
from .discovery import discover
from .session import CooperativeSession

# NOTE: redaction covers these node-bearing keys only; extend this tuple if the probe protocol grows new node-shaped keys (else their text bypasses redaction).
_NODE_LISTS = ("items", "decorators", "selected")


class Pacte:
    """Registers pacte_describe/probe/act; wires the cooperative client into the motor gate."""

    def __init__(self, exclusions: ExclusionFilter, session: CooperativeSession,
                 motor_organ_factory: Callable[[CooperativeClient], MotorOrgan],
                 discover_fn=discover, cooperative_dir: Path | None = None) -> None:
        self._exclusions = exclusions
        self._session = session
        self._motor_factory = motor_organ_factory
        self._discover = discover_fn
        self._dir = cooperative_dir
        self._client: CooperativeClient | None = None
        self._organ: MotorOrgan | None = None

    def register(self, mcp) -> None:
        @mcp.tool(name="pacte_describe", description=(
            "Connect to a cooperating app's --dev endpoint and return its capability manifest "
            "(probe fields + act verbs with their Hands level). Opens a cooperative session."))
        def pacte_describe() -> dict:
            ep = self._discover(self._dir)
            if ep is None:
                self._client = self._organ = None
                return {"connected": False, "reason": "no cooperative app found (launch it with --dev)"}
            client = CooperativeClient(ep)
            manifest = client.call("describe", {})
            self._client = client
            self._organ = self._motor_factory(client)
            self._session.open(app=ep.app, pid=ep.pid)
            return {"connected": True, "app": ep.app, "manifest": manifest}

        @mcp.tool(name="pacte_probe", description=(
            "Read the cooperating app's internal state (selected ids, item geometries, undo depth, "
            "dirty flag, decorators). Read-only; secret-zone items are redacted."))
        def pacte_probe(fields: list[str] | None = None) -> dict:
            if self._client is None:
                return {"status": "refused", "reason": "no cooperative session (call pacte_describe first)"}
            payload = self._client.call("probe", {"fields": fields} if fields else {})
            for key in _NODE_LISTS:
                if isinstance(payload.get(key), list):
                    payload[key] = self._exclusions.redact_nodes(payload[key])
            return payload

        @mcp.tool(name="pacte_act", description=(
            "Invoke an app verb (drag/resize/marquee/click/load_fixture/shortcut). Routed through "
            "Daimon's Hands ceiling + audit ledger; pass the verb's declared level. Refused outside "
            "an open cooperative session or above the session ceiling."))
        def pacte_act(verb: str, args: dict, intent: str, level: int, reversible: bool = True) -> dict:
            if self._organ is None:
                return {"status": "refused", "reason": "no cooperative session (call pacte_describe first)"}
            action = MotorAction(
                name=verb, level=Level(level), target=Target(observed=True),
                declaration=Declaration(reversible=reversible, intent=intent),
                params={"args": args},
            )
            return self._organ.act(action)
