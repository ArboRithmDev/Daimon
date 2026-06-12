"""Daimon MCP server — wires the senses onto a FastMCP stdio server.

Daimon is a *server*, not a client. It owns no perception loop: the AI client
connects over MCP and pulls a sense whenever it wants. This is what makes
Daimon agnostic — any MCP-capable client plugs in, no per-AI adapter.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .config import load_config
from .exclusions import ExclusionFilter
from .motor.actions import level_for
from .motor.factory import build_organ
from .motor.types import Declaration, MotorAction, Target
from .senses.base import Sense
from .senses.touche import Touche
from .senses.vue import Vue


def _register_motor(mcp) -> None:
    organ = build_organ()

    def _target(x, y, role, label):
        return Target(role=role, label=label, x=x, y=y)

    @mcp.tool(
        name="main_click",
        description=(
            "Click an element/coordinate. Provide the target's role/label (from "
            "Touché) so Daimon can verify reversibility. `reversible` and `intent` "
            "are your declaration; Daimon enforces the ceiling and may require human "
            "confirmation. Refused if above the configured ceiling."
        ),
    )
    def main_click(x: int, y: int, intent: str, reversible: bool = True,
                   role: str = "", label: str = "") -> dict:
        return organ.act(MotorAction(
            name="click", level=level_for("main_click"),
            target=_target(x, y, role or None, label or None),
            declaration=Declaration(reversible=reversible, intent=intent),
            params={"x": x, "y": y},
        ))

    @mcp.tool(
        name="main_type",
        description="Type text into the focused field. Declare intent/reversibility.",
    )
    def main_type(text: str, intent: str, reversible: bool = True,
                  role: str = "", label: str = "") -> dict:
        return organ.act(MotorAction(
            name="type", level=level_for("main_type"),
            target=_target(None, None, role or None, label or None),
            declaration=Declaration(reversible=reversible, intent=intent),
            params={"text": text},
        ))

    @mcp.tool(
        name="main_press",
        description=(
            "Activate an engaging button at (x,y) via the Accessibility API. "
            "VALIDATION level — non-return targets require human confirmation."
        ),
    )
    def main_press(x: int, y: int, intent: str, reversible: bool = False,
                   role: str = "", label: str = "") -> dict:
        return organ.act(MotorAction(
            name="press", level=level_for("main_press"),
            target=_target(x, y, role or None, label or None),
            declaration=Declaration(reversible=reversible, intent=intent),
            params={"x": x, "y": y},
        ))

    @mcp.tool(
        name="main_navigate",
        description="Non-destructive navigation: scroll by scroll_y pixels at the focused view.",
    )
    def main_navigate(intent: str, scroll_y: int = 0) -> dict:
        return organ.act(MotorAction(
            name="navigate", level=level_for("main_navigate"),
            target=Target(),
            declaration=Declaration(reversible=True, intent=intent),
            params={"scroll_y": scroll_y},
        ))


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

    _register_motor(mcp)

    return mcp


def main() -> None:
    build_server().run()  # stdio transport by default


if __name__ == "__main__":
    main()
