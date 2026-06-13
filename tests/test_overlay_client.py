from daimon.overlay.client import OverlayClient
from daimon.overlay.protocol import Banner


class _FakeSock:
    def __init__(self): self.sent = b""
    def sendall(self, b): self.sent += b


def test_send_writes_encoded_line():
    c = OverlayClient(socket_path="/tmp/x.sock")
    c._sock = _FakeSock()  # pretend connected
    c.send(Banner(text="hi", level="L2"))
    assert b"hi" in c._sock.sent and c._sock.sent.endswith(b"\n")


def test_send_without_connection_is_silent(monkeypatch):
    c = OverlayClient(socket_path="/tmp/does-not-exist.sock")
    # connect will fail; send must not raise
    c.send(Banner(text="hi"))


def test_failed_send_drops_socket(monkeypatch):
    c = OverlayClient(socket_path="/tmp/x.sock")
    class _Boom:
        def sendall(self, b): raise OSError("broken pipe")
    c._sock = _Boom()
    c.send(Banner(text="hi"))   # must not raise
    assert c._sock is None       # dropped so next send retries connect
