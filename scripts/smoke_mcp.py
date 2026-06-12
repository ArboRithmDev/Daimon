"""End-to-end smoke test of the real MCP stdio transport.

Spawns `python -m daimon` as a subprocess, performs the MCP handshake over
stdio, lists the tools, and exercises each sense. This is exactly how an AI
client (Claude Code, etc.) talks to Daimon — no in-process shortcuts.

Run:  python scripts/smoke_mcp.py
"""

from __future__ import annotations

import asyncio
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main() -> int:
    params = StdioServerParameters(command=sys.executable, args=["-m", "daimon"])

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            print("tools:", names)
            assert {"vue_displays", "vue_snapshot", "touche_tree", "touche_probe"} <= set(names)

            displays = await session.call_tool("vue_displays", {})
            print("vue_displays:", displays.content[0].text)

            snap = await session.call_tool("vue_snapshot", {"display": 0, "max_width": 600})
            kinds = [c.type for c in snap.content]
            print("vue_snapshot content types:", kinds)
            assert "image" in kinds, "expected an image back from vue_snapshot"

            tree = await session.call_tool("touche_tree", {})
            print("touche_tree:", tree.content[0].text[:200])

            probe = await session.call_tool("touche_probe", {"x": 100, "y": 100})
            print("touche_probe:", probe.content[0].text[:200])

    print("\nSMOKE OK — real MCP transport works.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
