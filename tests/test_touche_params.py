import asyncio
from daimon.config import ExclusionConfig
from daimon.exclusions import ExclusionFilter
from daimon.senses.touche import Touche
from mcp.server.fastmcp import FastMCP


def test_touche_tree_accepts_bounding_params(monkeypatch):
    import daimon.capture.accessibility as ax
    captured = {}
    monkeypatch.setattr(ax, "is_trusted", lambda: True)
    def fake_snapshot(**kw):
        captured.update(kw); return {"role": "AXWindow"}
    monkeypatch.setattr(ax, "snapshot_tree", fake_snapshot)

    mcp = FastMCP("t")
    Touche(ExclusionFilter(ExclusionConfig())).register(mcp)
    asyncio.run(mcp.call_tool("touche_tree", {"max_depth": 2, "summary": True}))
    assert captured["max_depth"] == 2
    assert captured["summary"] is True
