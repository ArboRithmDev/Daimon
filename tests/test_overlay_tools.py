import asyncio
import sys

import pytest

from daimon.server import build_server


@pytest.mark.skipif(sys.platform == "win32",
                    reason="build_server wires motor backends (build_organ); lands in W2")
def test_overlay_tools_registered():
    names = {t.name for t in asyncio.run(build_server().list_tools())}
    assert {"overlay_highlight", "overlay_spotlight", "overlay_cursor",
            "overlay_banner", "overlay_clear"} <= names
