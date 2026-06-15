import asyncio
from daimon.config import ExclusionConfig
from daimon.exclusions import ExclusionFilter
from daimon.senses.touche import Touche
from mcp.server.fastmcp import FastMCP


def test_touche_tree_accepts_bounding_params(monkeypatch):
    import daimon.backends as backends
    captured = {}

    def fake_snapshot(**kw):
        captured.update(kw); return {"role": "AXWindow"}

    class _FakeA11y:
        is_trusted = staticmethod(lambda: True)
        snapshot_tree = staticmethod(fake_snapshot)

    # Patch the platform selector so the test is OS-agnostic (Touché now pulls
    # its backend via backends.build_a11y rather than importing capture directly).
    monkeypatch.setattr(backends, "build_a11y", lambda: _FakeA11y)

    mcp = FastMCP("t")
    Touche(ExclusionFilter(ExclusionConfig())).register(mcp)
    asyncio.run(mcp.call_tool("touche_tree", {"max_depth": 2, "summary": True}))
    assert captured["max_depth"] == 2
    assert captured["summary"] is True
