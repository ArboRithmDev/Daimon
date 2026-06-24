"""In-process JSON-RPC TCP test double for the cooperative channel. No Qt.

Honors the FROZEN v1.1 wire contract so Daimon-side tests can exercise capture,
the new probe fields (events/inspector/tree/serialized/quiescent), the
``events_since`` delta, and the act verbs (set_prop/set_motion) WITHOUT a real
Delta. A test may still override any method via ``handlers[name] = fn``; an
override wins over the built-in default.
"""

from __future__ import annotations

import base64
import json
import socket
import threading

from daimon.pacte.discovery import Endpoint
from daimon.pacte.protocol import PROTOCOL_VERSION

# A real, minimal 1x1 PNG. Daimon only base64-decodes + wraps it as an image; it
# never parses the pixels, so a constant keeps the double dependency-free (no PIL).
_PNG_1X1 = base64.b64encode(bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000d49444154789c63f8cfc0f01f0005000180ff6c6f7a0000000049454e44ae426082"
)).decode("ascii")


class FakeCooperativeEndpoint:
    def __init__(self, token: str = "secret", app: str = "fake"):
        self.token = token
        self.app = app
        self.requests: list[dict] = []
        self.handlers: dict = {}
        # Mutable in-process model the built-in defaults read/write. Tests can poke
        # ``state`` directly (e.g. flip ``quiescent``) to drive poll-until scenarios.
        self.state: dict = {
            "selected": [],
            "items": [],
            "decorators": {},
            "inspector": {"bound_node_id": None, "mode": "none", "fields": []},
            "tree": {"id": "root", "type": "Screen", "canvas": None,
                     "layout_rule": None, "rendered_rect": None, "children": []},
            "serialized": "",
            "quiescent": True,
        }
        self.events: list[dict] = []   # ring of {seq, kind, type, node_id, summary}
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = False

    # -- helpers tests use to script the scenario -------------------------
    def push_event(self, kind: str, type: str, node_id: str | None = None, summary: str = "") -> None:
        seq = (self.events[-1]["seq"] + 1) if self.events else 1
        self.events.append({"seq": seq, "kind": kind, "type": type,
                            "node_id": node_id, "summary": summary})
        del self.events[:-200]   # ring buffer 200

    def start(self) -> Endpoint:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(8)
        port = self._sock.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        return Endpoint(port=port, token=self.token, pid=0, app=self.app,
                        protocol_version=PROTOCOL_VERSION)

    def _serve(self):
        while not self._stop:
            try:
                conn, _ = self._sock.accept()
            except OSError:
                return
            with conn:
                data = conn.makefile("r")
                line = data.readline()
                if not line:
                    continue
                req = json.loads(line)
                self.requests.append(req)
                rid = req.get("id")
                params = req.get("params", {})
                if params.get("token") != self.token:
                    resp = {"jsonrpc": "2.0", "id": rid,
                            "error": {"code": -32001, "message": "bad token"}}
                else:
                    handler = self.handlers.get(req.get("method"))
                    result = handler(params) if handler else self._default(req.get("method"), params)
                    resp = {"jsonrpc": "2.0", "id": rid, "result": result}
                conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

    # -- built-in contract-honoring defaults ------------------------------
    def _default(self, method: str, params: dict) -> dict:
        if method == "describe":
            return self._describe()
        if method == "probe":
            return self._probe(params)
        if method == "capture":
            return self._capture(params)
        if method == "act":
            return self._act(params)
        return {}

    def _describe(self) -> dict:
        return {
            "probe_fields": ["selected", "items", "decorators", "inspector",
                             "tree", "serialized", "events", "quiescent"],
            "act_verbs": [
                {"name": "set_prop", "level": 2},
                {"name": "set_motion", "level": 1},
            ],
        }

    def _probe(self, params: dict) -> dict:
        fields = params.get("fields")
        since = params.get("events_since")
        out: dict = {}
        wanted = fields if fields else [k for k in self.state] + ["events"]
        for key in wanted:
            if key == "events":
                evs = self.events
                if since is not None:
                    evs = [e for e in evs if e["seq"] > since]
                out["events"] = evs[-50:]
            elif key in self.state:
                out[key] = self.state[key]
        # ``events_since`` alone (no explicit fields) still returns the events delta.
        if since is not None and "events" not in out:
            out["events"] = [e for e in self.events if e["seq"] > since]
        return out

    def _capture(self, params: dict) -> dict:
        return {"ok": True, "image_base64": _PNG_1X1, "mime": "image/png",
                "width": 1, "height": 1,
                "scene_rect": {"x": 0, "y": 0, "w": 1, "h": 1}}

    def _act(self, params: dict) -> dict:
        verb, args = params.get("verb"), params.get("args", {})
        if verb == "set_motion":
            self.state["quiescent"] = True if args.get("enabled") is False else self.state["quiescent"]
            return {"ok": True, "verb": verb, "enabled": args.get("enabled")}
        if verb == "set_prop":
            self.push_event("command", "ChangeProperty", node_id=args.get("node_id"),
                            summary=f"set {args.get('path')}")
            return {"ok": True, "verb": verb,
                    "state_delta": {"node_id": args.get("node_id"),
                                    "path": args.get("path"), "value": args.get("value")}}
        return {"ok": True, "verb": verb}

    def stop(self):
        self._stop = True
        if self._sock is not None:
            self._sock.close()
