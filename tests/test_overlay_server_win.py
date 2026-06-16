"""OverlayServer over the TCP listener seam — proves the shared lifecycle
(concurrent accept, live-count, idle-quit) drives the Windows transport.

Pure sockets + injected seams, no Qt, runs on any platform.
"""

import socket
import time

from daimon.overlay.app.server import OverlayServer
from daimon.overlay.protocol import Banner, encode


class _FakeScene:
    def __init__(self):
        self.applied = []

    def apply(self, cmd):
        self.applied.append(cmd)


def _wait(pred, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.01)
    return False


def test_connection_applies_command_then_idle_quit():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(8)
    port = srv.getsockname()[1]

    scene = _FakeScene()
    terminated = {"called": False}

    import threading
    server = OverlayServer(
        scene, flip_height=None, idle_grace=0.0,
        # Honour the delay: the 60s startup-reap must NOT fire during the test,
        # but the 0s idle-quit after disconnect should.
        scheduler=lambda delay, fn: threading.Timer(delay, fn).start(),
        terminate=lambda: terminated.__setitem__("called", True),
        main_dispatch=lambda fn, arg: fn(arg),     # apply synchronously
        listen_sock=srv,
    )
    server.start()

    c = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    c.connect(("127.0.0.1", port))
    c.sendall(encode(Banner(text="hi", level="L2")).encode("utf-8"))

    assert _wait(lambda: any(isinstance(x, Banner) for x in scene.applied))

    c.close()
    # last client gone → scene cleared + terminate fired
    assert _wait(lambda: terminated["called"])
