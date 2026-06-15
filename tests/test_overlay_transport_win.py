"""TCP-loopback overlay transport + Windows client. Pure sockets, any platform."""

import socket
import threading

from daimon.overlay import transport_win
from daimon.overlay.client_win import OverlayClient
from daimon.overlay.protocol import Banner, decode


def _ephemeral_listener():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    return srv, srv.getsockname()[1]


def test_is_alive_false_then_true(monkeypatch):
    srv, port = _ephemeral_listener()
    monkeypatch.setattr(transport_win, "_PORT", port)
    try:
        assert transport_win.is_alive() is True
    finally:
        srv.close()
    assert transport_win.is_alive() is False  # nothing listening now


def test_client_send_delivers_encoded_command(monkeypatch):
    srv, port = _ephemeral_listener()
    monkeypatch.setattr(transport_win, "_PORT", port)
    received = {}
    ready = threading.Event()

    def _accept():
        conn, _ = srv.accept()
        ready.set()
        data = conn.recv(4096)
        received["line"] = data.decode("utf-8").strip()
        conn.close()

    t = threading.Thread(target=_accept, daemon=True)
    t.start()

    client = OverlayClient()
    client.send(Banner(text="hello", level="L2"))
    t.join(2)
    srv.close()

    cmd = decode(received["line"])
    assert isinstance(cmd, Banner) and cmd.text == "hello" and cmd.level == "L2"


def test_send_without_overlay_is_silent(monkeypatch):
    # Point at a closed port: connect fails, send must not raise.
    srv, port = _ephemeral_listener()
    srv.close()
    monkeypatch.setattr(transport_win, "_PORT", port)
    OverlayClient().send(Banner(text="nobody home"))  # no exception
