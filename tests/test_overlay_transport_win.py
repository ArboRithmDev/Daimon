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


def test_is_alive_follows_the_published_port(monkeypatch, tmp_path):
    monkeypatch.setenv("DAIMON_DATA_DIR", str(tmp_path))
    assert transport_win.is_alive() is False           # no port file yet
    srv, port = _ephemeral_listener()
    transport_win.write_port(port)
    try:
        assert transport_win.read_port() == port
        assert transport_win.is_alive() is True
    finally:
        srv.close()
    assert transport_win.is_alive() is False           # nothing listening now


def test_client_send_delivers_encoded_command(monkeypatch, tmp_path):
    monkeypatch.setenv("DAIMON_DATA_DIR", str(tmp_path))
    srv, port = _ephemeral_listener()
    transport_win.write_port(port)
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

    OverlayClient().send(Banner(text="hello", level="L2"))
    t.join(2)
    srv.close()

    cmd = decode(received["line"])
    assert isinstance(cmd, Banner) and cmd.text == "hello" and cmd.level == "L2"


def test_send_without_overlay_is_silent(monkeypatch, tmp_path):
    monkeypatch.setenv("DAIMON_DATA_DIR", str(tmp_path))
    # No port file → connect fails, send must not raise.
    OverlayClient().send(Banner(text="nobody home"))
