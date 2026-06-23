"""Loopback TCP transport for the cooperative channel. One request → one response line."""

from __future__ import annotations

import json
import socket

from .discovery import Endpoint
from .protocol import ProtocolError, build_request, parse_response


class CooperativeClient:
    """Sends newline-delimited JSON-RPC requests to a discovered loopback endpoint."""

    def __init__(self, endpoint: Endpoint) -> None:
        self._ep = endpoint
        self._rid = 0

    def call(self, method: str, params: dict, timeout: float = 5.0) -> dict:
        """Round-trip one JSON-RPC call; raise ProtocolError on any transport/JSON failure."""
        self._rid += 1
        rid = self._rid
        req = build_request(method, params, token=self._ep.token, rid=rid)
        try:
            with socket.create_connection(("127.0.0.1", self._ep.port), timeout=timeout) as s:
                s.settimeout(timeout)
                s.sendall((json.dumps(req) + "\n").encode("utf-8"))
                raw = s.makefile("r").readline()
        except OSError as e:
            raise ProtocolError(f"transport failure: {e}") from e
        if not raw:
            raise ProtocolError("empty response")
        try:
            decoded = json.loads(raw)
        except ValueError as e:
            raise ProtocolError(f"bad JSON response: {e}") from e
        return parse_response(decoded, rid)
