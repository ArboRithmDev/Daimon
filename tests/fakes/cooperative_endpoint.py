"""In-process JSON-RPC TCP test double for the cooperative channel. No Qt."""

from __future__ import annotations

import json
import socket
import threading

from daimon.pacte.discovery import Endpoint
from daimon.pacte.protocol import PROTOCOL_VERSION


class FakeCooperativeEndpoint:
    def __init__(self, token: str = "secret", app: str = "fake"):
        self.token = token
        self.app = app
        self.requests: list[dict] = []
        self.handlers: dict = {}
        self._sock: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._stop = False

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
                    handler = self.handlers.get(req.get("method"), lambda p: {})
                    resp = {"jsonrpc": "2.0", "id": rid, "result": handler(params)}
                conn.sendall((json.dumps(resp) + "\n").encode("utf-8"))

    def stop(self):
        self._stop = True
        if self._sock is not None:
            self._sock.close()
