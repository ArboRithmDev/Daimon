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
            "Click an element/coordinate. button=left|right|middle, count=1|2 "
            "(double-click), modifiers=[cmd,shift,opt,ctrl]. Provide role/label "
            "(from Touché) so Daimon can verify reversibility. Refused above the ceiling."
        ),
    )
    def main_click(x: int, y: int, intent: str, reversible: bool = True,
                   button: str = "left", count: int = 1, modifiers: list[str] | None = None,
                   role: str = "", label: str = "") -> dict:
        return organ.act(MotorAction(
            name="click", level=level_for("main_click"),
            target=_target(x, y, role or None, label or None),
            declaration=Declaration(reversible=reversible, intent=intent),
            params={"x": x, "y": y, "button": button, "count": count,
                    "modifiers": modifiers or []},
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

    @mcp.tool(name="main_key", description=(
        "Send a discrete key or chord (Return/Tab/Esc/arrows/F-keys or e.g. "
        "cmd+shift+r). Distinct from main_type (text). Dangerous combos require "
        "confirmation."))
    def main_key(key: str, intent: str, modifiers: list[str] | None = None,
                 count: int = 1, reversible: bool = True) -> dict:
        mods = modifiers or []
        keystr = "+".join([*mods, key])
        return organ.act(MotorAction(
            name="key", level=level_for("main_key"), target=Target(),
            declaration=Declaration(reversible=reversible, intent=intent),
            params={"key": key, "modifiers": mods, "count": count, "keystr": keystr},
        ))

    @mcp.tool(name="main_hover", description="Move the pointer to (x,y) without clicking (reveal tooltips/menus).")
    def main_hover(x: int, y: int, intent: str) -> dict:
        return organ.act(MotorAction(
            name="hover", level=level_for("main_hover"), target=_target(x, y, None, None),
            declaration=Declaration(reversible=True, intent=intent), params={"x": x, "y": y}))

    @mcp.tool(name="main_activate", description="Bring an app/window frontmost by bundle id, title, or pid.")
    def main_activate(intent: str, bundle: str = "", title: str = "", pid: int = 0) -> dict:
        params = {k: v for k, v in (("bundle", bundle), ("title", title), ("pid", pid)) if v}
        return organ.act(MotorAction(
            name="activate", level=level_for("main_activate"), target=Target(),
            declaration=Declaration(reversible=True, intent=intent), params=params))


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
