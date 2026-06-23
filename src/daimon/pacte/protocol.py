"""JSON-RPC 2.0 envelope + schema for the cooperative channel. Pure — no I/O."""

from __future__ import annotations

PROTOCOL_VERSION = "1.0"


class ProtocolError(Exception):
    """A malformed, mismatched, or error JSON-RPC response."""


def build_request(method: str, params: dict, token: str, rid: int) -> dict:
    """Build a JSON-RPC 2.0 request with the auth token folded into params."""
    return {"jsonrpc": "2.0", "id": rid, "method": method, "params": {**params, "token": token}}


def parse_response(raw: dict, rid: int) -> dict:
    """Return the result for `rid`; raise ProtocolError on mismatch/error/missing result."""
    if raw.get("id") != rid:
        raise ProtocolError(f"response id {raw.get('id')!r} != request id {rid!r}")
    if "error" in raw:
        err = raw["error"]
        raise ProtocolError(f"endpoint error {err.get('code')}: {err.get('message')}")
    if "result" not in raw:
        raise ProtocolError("response has neither result nor error")
    return raw["result"]
