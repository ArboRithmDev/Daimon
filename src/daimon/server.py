"""Daimon MCP server — wires the senses onto a FastMCP stdio server.

Daimon is a *server*, not a client. It owns no perception loop: the AI client
connects over MCP and pulls a sense whenever it wants. This is what makes
Daimon agnostic — any MCP-capable client plugs in, no per-AI adapter.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .config import load_config
from .exclusions import ExclusionFilter
from .senses.base import Sense
from .senses.touche import Touche
from .senses.vue import Vue


def build_server() -> FastMCP:
    config = load_config()
    exclusions = ExclusionFilter(config.exclusions)

    mcp = FastMCP("daimon")

    senses: list[Sense] = [
        Vue(exclusions),
        Touche(exclusions),
    ]
    for sense in senses:
        sense.register(mcp)

    return mcp


def main() -> None:
    build_server().run()  # stdio transport by default


if __name__ == "__main__":
    main()
