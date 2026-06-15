import asyncio

from daimon.server import build_server


def test_overlay_tools_registered(tmp_path, monkeypatch):
    monkeypatch.setenv("DAIMON_DATA_DIR", str(tmp_path))  # no real-home pollution
    names = {t.name for t in asyncio.run(build_server().list_tools())}
    assert {"overlay_highlight", "overlay_spotlight", "overlay_cursor",
            "overlay_banner", "overlay_clear"} <= names
