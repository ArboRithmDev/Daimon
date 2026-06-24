"""Pacte — the cooperative channel organ. Generic: speaks the protocol, never imports Qt.

pacte_describe handshakes + opens a cooperative session; pacte_probe reads redacted state;
pacte_act runs each verb through the SAME MotorOrgan chokepoint (ceiling + ledger), satisfied
by the durable session consent rather than a per-action dialog.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Callable

from mcp.server.fastmcp import Image as MCPImage
from mcp.types import TextContent

from ..exclusions import ExclusionFilter
from ..motor.organ import MotorOrgan
from ..motor.types import Declaration, Level, MotorAction, Target
from .client import CooperativeClient
from .discovery import discover
from .expect import evaluate, field_roots
from .session import CooperativeSession

# NOTE: redaction covers these node-bearing keys only; extend this tuple if the probe protocol grows new node-shaped keys (else their text bypasses redaction).
_NODE_LISTS = ("items", "decorators", "selected")


class Pacte:
    """Registers pacte_describe/probe/act; wires the cooperative client into the motor gate."""

    def __init__(self, exclusions: ExclusionFilter, session: CooperativeSession,
                 motor_organ_factory: Callable[[CooperativeClient], MotorOrgan],
                 discover_fn=discover, cooperative_dir: Path | None = None,
                 clock_ms: Callable[[], float] | None = None,
                 sleep_ms: Callable[[float], None] | None = None) -> None:
        self._exclusions = exclusions
        self._session = session
        self._motor_factory = motor_organ_factory
        self._discover = discover_fn
        self._dir = cooperative_dir
        self._client: CooperativeClient | None = None
        self._organ: MotorOrgan | None = None
        # Injectable time source so pacte_expect's poll loop is deterministic in tests.
        self._clock_ms = clock_ms or (lambda: __import__("time").monotonic() * 1000.0)
        self._sleep_ms = sleep_ms or (lambda ms: __import__("time").sleep(ms / 1000.0))

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
            return self._do_probe(fields)

        @mcp.tool(name="pacte_capture", description=(
            "Capture targeted SCENE pixels from the cooperating app and RETURN them as an "
            "image you look at yourself (like vue_snapshot). `target` is a node_id, "
            "{\"scene\":{x,y,w,h}}, or \"viewport\". `max_width` downscales keeping ratio "
            "(default 1024); `padding` adds scene-unit margin around a node bbox. Read-only "
            "(Hands level 0); secret-zone items are painted neutral by the app. Returns a "
            "scene_rect metadata block + the PNG. Refused outside an open cooperative session."))
        def pacte_capture(target, max_width: int = 1024, padding: int = 0) -> list | dict:
            if self._client is None:
                return {"status": "refused", "reason": "no cooperative session (call pacte_describe first)"}
            res = self._client.call("capture", {"target": target, "max_width": max_width, "padding": padding})
            png = base64.b64decode(res["image_base64"])
            meta = {"scene_rect": res.get("scene_rect"), "width": res.get("width"),
                    "height": res.get("height"), "mime": res.get("mime", "image/png")}
            return [TextContent(type="text", text=json.dumps(meta)),
                    MCPImage(data=png, format="png")]

        @mcp.tool(name="pacte_events", description=(
            "Read the app's recent command/event log to verify causality — catch the dominant "
            "bug class 'visual mutation with NO command/undo'. Returns {events:[{seq,kind:"
            "command|event,type,node_id,summary}]} in chronological order. Pass `since` (a seq) "
            "to get only newer entries (seq>since) — diff the log around an edit. Refused outside "
            "an open cooperative session."))
        def pacte_events(since: int | None = None) -> dict:
            if self._client is None:
                return {"status": "refused", "reason": "no cooperative session (call pacte_describe first)"}
            params = {"events_since": since} if since is not None else {"fields": ["events"]}
            return self._client.call("probe", params)

        @mcp.tool(name="pacte_expect", description=(
            "Poll the cooperating app until a condition holds or timeout — kills temporal "
            "flakiness (no blind sleeps; the app never blocks). condition DSL: a leaf "
            "{field,op:eq|ne|gte|lte|contains|len_eq,value}, the shortcut {quiescent:true}, "
            "or {all:[...]}/{any:[...]}; `field` may be dotted (e.g. "
            "\"decorators.nested_overlay.visible\"). timeout_ms default 2000, poll_ms default "
            "50 (clamped to [20,500]); only the referenced fields are probed. Returns "
            "{ok,satisfied,elapsed_ms,final}. Refused outside an open cooperative session."))
        def pacte_expect(condition: dict, timeout_ms: int = 2000, poll_ms: int = 50) -> dict:
            if self._client is None:
                return {"status": "refused", "reason": "no cooperative session (call pacte_describe first)"}
            poll = max(20, min(500, poll_ms))
            fields = sorted(field_roots(condition))
            start = self._clock_ms()
            final: dict = {}
            while True:
                final = self._do_probe(fields)
                if evaluate(condition, final):
                    return {"ok": True, "satisfied": True,
                            "elapsed_ms": int(self._clock_ms() - start), "final": final}
                if self._clock_ms() - start >= timeout_ms:
                    return {"ok": False, "satisfied": False,
                            "elapsed_ms": int(self._clock_ms() - start), "final": final}
                self._sleep_ms(poll)

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

    def _do_probe(self, fields: list[str] | None) -> dict:
        """Call the endpoint's probe, applying the legacy flat-key redaction (ADR-1)."""
        payload = self._client.call("probe", {"fields": fields} if fields else {})
        for key in _NODE_LISTS:
            if isinstance(payload.get(key), list):
                payload[key] = self._exclusions.redact_nodes(payload[key])
        return payload
