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
from .senses.delegation import build_server_instructions
from .senses.touche import Touche
from .senses.vue import Vue


def _register_overlay(mcp) -> None:
    """Wire the optional HUD overlay tools onto the server."""
    from .config import load_overlay_config
    from .overlay import launcher
    from .overlay.client import OverlayClient
    from .overlay.protocol import Highlight, Spotlight, Cursor, Banner, Clear

    client = OverlayClient(launcher.socket_path())  # silent no-op if overlay not running

    @mcp.tool(name="overlay_highlight", description="Outline a screen rect with an optional label.")
    def overlay_highlight(x: int, y: int, width: int, height: int, label: str = "") -> dict:
        """Outline a screen rect."""
        client.send(Highlight(x=x, y=y, w=width, h=height, label=label))
        return {"ok": True}

    @mcp.tool(name="overlay_spotlight", description="Dim everything except a screen rect (focus).")
    def overlay_spotlight(x: int, y: int, width: int, height: int) -> dict:
        """Dim everything but one rect."""
        client.send(Spotlight(x=x, y=y, w=width, h=height))
        return {"ok": True}

    @mcp.tool(name="overlay_cursor", description="Move the overlay cursor halo to (x,y).")
    def overlay_cursor(x: int, y: int) -> dict:
        """Move the cursor halo."""
        client.send(Cursor(x=x, y=y))
        return {"ok": True}

    @mcp.tool(name="overlay_banner", description="Show a HUD banner message.")
    def overlay_banner(text: str, level: str = "L1") -> dict:
        """Show a HUD banner."""
        client.send(Banner(text=text, level=level))
        return {"ok": True}

    @mcp.tool(name="overlay_clear", description="Clear all overlay drawings.")
    def overlay_clear() -> dict:
        """Clear all overlay drawings."""
        client.send(Clear())
        return {"ok": True}


def _resolve_point(x, y, display, space, max_width=720, region=None):
    """Map (x, y) to a GLOBAL desktop pixel for a positional Hand.

    `space="global"` (default) passes through — back-compat, the client supplied
    global coords directly. `space="image"` treats (x, y) as pixels in a
    vue_snapshot of `display` (taken at `max_width`/`region`) and applies that
    display's origin + the snapshot's downscale internally, so the client never
    handles negative global coords or the downscale factor itself. `display=None`
    with image space is an error (image coords are meaningless without a display).
    """
    if x is None or y is None or space != "image":
        return x, y
    if display is None:
        raise ValueError("space='image' requires a display index")
    from .capture import screen
    from .capture.coordspace import CoordSpace
    displays = screen.list_displays()
    if display < 0 or display >= len(displays):
        raise IndexError(f"display {display} out of range (0..{len(displays) - 1})")
    d = displays[display]
    source_w = int(region["width"]) if region else d.width
    image_scale = max_width / source_w if (max_width and source_w > max_width) else 1.0
    cs = CoordSpace(
        display_origin_x=d.origin_x, display_origin_y=d.origin_y,
        image_scale=image_scale,
        region_x=int(region["x"]) if region else 0,
        region_y=int(region["y"]) if region else 0,
    )
    return cs.to_global(x, y)


def _register_motor(mcp) -> None:
    """Wire the motor (hands) action tools onto the server."""
    organ = build_organ()

    def _target(x, y, role, label):
        return Target(role=role, label=label, x=x, y=y)

    def _attach_focus(params, bundle, title, pid, ensure_focus):
        """Add the target-window descriptor + ensure_focus flag for F3, if given."""
        window = {k: v for k, v in (("bundle", bundle), ("title", title), ("pid", pid)) if v}
        if window:
            params["window"] = window
            if ensure_focus:
                params["ensure_focus"] = True

    @mcp.tool(
        name="main_click",
        description=(
            "Click an element/coordinate. button=left|right|middle, count=1|2 "
            "(double-click), modifiers=[cmd,shift,opt,ctrl]. Provide role/label "
            "(from Touché) so Daimon can verify reversibility. Refused above the "
            "ceiling. space='image' with display=k passes snapshot-local pixels "
            "(set max_width/region to match that snapshot) and Daimon resolves the "
            "global pixel itself — no manual offset/scale, negative displays handled. "
            "Pass window={bundle|title|pid} so Daimon checks the target is frontmost "
            "(a click on a background window is a silent no-op); ensure_focus=True "
            "activates it first instead of just warning."
        ),
    )
    def main_click(x: int, y: int, intent: str, reversible: bool = True,
                   button: str = "left", count: int = 1, modifiers: list[str] | None = None,
                   role: str = "", label: str = "", display: int | None = None,
                   space: str = "global", max_width: int = 720,
                   region: dict | None = None, window_bundle: str = "",
                   window_title: str = "", window_pid: int = 0,
                   ensure_focus: bool = False) -> dict:
        """Click an element or coordinate."""
        x, y = _resolve_point(x, y, display, space, max_width, region)
        params = {"x": x, "y": y, "button": button, "count": count,
                  "modifiers": modifiers or []}
        _attach_focus(params, window_bundle, window_title, window_pid, ensure_focus)
        return organ.act(MotorAction(
            name="click", level=level_for("main_click"),
            target=_target(x, y, role or None, label or None),
            declaration=Declaration(reversible=reversible, intent=intent),
            params=params,
        ))

    @mcp.tool(
        name="main_type",
        description="Type text into the focused field. Declare intent/reversibility.",
    )
    def main_type(text: str, intent: str, reversible: bool = True,
                  role: str = "", label: str = "") -> dict:
        """Type text into the focused field."""
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
                   role: str = "", label: str = "", display: int | None = None,
                   space: str = "global", max_width: int = 720,
                   region: dict | None = None, window_bundle: str = "",
                   window_title: str = "", window_pid: int = 0,
                   ensure_focus: bool = False) -> dict:
        """Activate a button via the Accessibility API."""
        x, y = _resolve_point(x, y, display, space, max_width, region)
        params = {"x": x, "y": y}
        _attach_focus(params, window_bundle, window_title, window_pid, ensure_focus)
        return organ.act(MotorAction(
            name="press", level=level_for("main_press"),
            target=_target(x, y, role or None, label or None),
            declaration=Declaration(reversible=reversible, intent=intent),
            params=params,
        ))

    @mcp.tool(
        name="main_navigate",
        description=(
            "Non-destructive scroll by scroll_y pixels. Give an explicit target "
            "view with (x, y) — Daimon moves the pointer there first so the scroll "
            "lands on the view you mean, not 'the focused view' (the last-touched "
            "element, often the wrong pane). x/y accept space='image' + display=k "
            "like the other Hands. Omit x/y to scroll wherever the pointer is."
        ),
    )
    def main_navigate(intent: str, scroll_y: int = 0, x: int | None = None,
                      y: int | None = None, display: int | None = None,
                      space: str = "global", max_width: int = 720,
                      region: dict | None = None) -> dict:
        """Scroll a targeted view (non-destructive)."""
        x, y = _resolve_point(x, y, display, space, max_width, region)
        params = {"scroll_y": scroll_y}
        if x is not None and y is not None:
            params["x"], params["y"] = x, y
        return organ.act(MotorAction(
            name="navigate", level=level_for("main_navigate"),
            target=Target(x=x, y=y),
            declaration=Declaration(reversible=True, intent=intent),
            params=params,
        ))

    @mcp.tool(name="main_key", description=(
        "Send a discrete key or chord (Return/Tab/Esc/arrows/F-keys or e.g. "
        "cmd+shift+r). Distinct from main_type (text). Dangerous combos require "
        "confirmation."))
    def main_key(key: str, intent: str, modifiers: list[str] | None = None,
                 count: int = 1, reversible: bool = True) -> dict:
        """Send a discrete key or chord."""
        mods = modifiers or []
        keystr = "+".join([*mods, key])
        return organ.act(MotorAction(
            name="key", level=level_for("main_key"), target=Target(),
            declaration=Declaration(reversible=reversible, intent=intent),
            params={"key": key, "modifiers": mods, "count": count, "keystr": keystr},
        ))

    @mcp.tool(name="main_hover", description=(
        "Move the pointer to (x,y) without clicking (reveal tooltips/menus). "
        "space='image' + display=k resolves snapshot-local pixels to global."))
    def main_hover(x: int, y: int, intent: str, display: int | None = None,
                   space: str = "global", max_width: int = 720,
                   region: dict | None = None) -> dict:
        """Move the pointer without clicking."""
        x, y = _resolve_point(x, y, display, space, max_width, region)
        return organ.act(MotorAction(
            name="hover", level=level_for("main_hover"), target=_target(x, y, None, None),
            declaration=Declaration(reversible=True, intent=intent), params={"x": x, "y": y}))

    @mcp.tool(name="main_activate", description="Bring an app/window frontmost by bundle id, title, or pid.")
    def main_activate(intent: str, bundle: str = "", title: str = "", pid: int = 0) -> dict:
        """Bring an app or window frontmost."""
        params = {k: v for k, v in (("bundle", bundle), ("title", title), ("pid", pid)) if v}
        return organ.act(MotorAction(
            name="activate", level=level_for("main_activate"), target=Target(),
            declaration=Declaration(reversible=True, intent=intent), params=params))

    def _window_params(bundle: str, title: str, pid: int) -> dict:
        """Build the window-targeting params dict."""
        return {k: v for k, v in (("bundle", bundle), ("title", title), ("pid", pid)) if v}

    def _window_action(verb: str, intent: str, bundle: str, title: str, pid: int) -> dict:
        """Execute a window action via organ.act."""
        return organ.act(MotorAction(
            name=verb, level=level_for("main_" + verb), target=Target(),
            declaration=Declaration(reversible=True, intent=intent),
            params=_window_params(bundle, title, pid),
        ))

    @mcp.tool(name="main_window_minimize", description=(
        "Minimize the target app's front window (AX, immune to app key rebinds — unlike a "
        "Cmd+M chord). Target by bundle, title, or pid. Reversible (main_window_show restores)."))
    def main_window_minimize(intent: str, bundle: str = "", title: str = "", pid: int = 0) -> dict:
        """Minimize the target app's front window."""
        return _window_action("window_minimize", intent, bundle, title, pid)

    @mcp.tool(name="main_window_hide", description=(
        "Hide the target app (NSRunningApplication.hide — immune to app key rebinds, unlike "
        "Cmd+H). Target by bundle, title, or pid. Reversible (main_window_show restores)."))
    def main_window_hide(intent: str, bundle: str = "", title: str = "", pid: int = 0) -> dict:
        """Hide the target app."""
        return _window_action("window_hide", intent, bundle, title, pid)

    @mcp.tool(name="main_window_show", description=(
        "Unhide + un-minimize + raise the target app (restore after minimize/hide). Target by "
        "bundle, title, or pid."))
    def main_window_show(intent: str, bundle: str = "", title: str = "", pid: int = 0) -> dict:
        """Unhide + un-minimize + raise the target app."""
        return _window_action("window_show", intent, bundle, title, pid)

    @mcp.tool(name="main_drag", description=(
        "Drag from (from_x,from_y) to (to_x,to_y). The drop destination is "
        "classified for reversibility (e.g. dropping on Trash gates)."))
    def main_drag(from_x: int, from_y: int, to_x: int, to_y: int, intent: str,
                  button: str = "left", reversible: bool = True,
                  display: int | None = None, space: str = "global",
                  max_width: int = 720, region: dict | None = None,
                  window_bundle: str = "", window_title: str = "",
                  window_pid: int = 0, ensure_focus: bool = False) -> dict:
        """Drag from one point to another."""
        from_x, from_y = _resolve_point(from_x, from_y, display, space, max_width, region)
        to_x, to_y = _resolve_point(to_x, to_y, display, space, max_width, region)
        params = {"from_x": from_x, "from_y": from_y, "to_x": to_x, "to_y": to_y,
                  "button": button}
        _attach_focus(params, window_bundle, window_title, window_pid, ensure_focus)
        return organ.act(MotorAction(
            name="drag", level=level_for("main_drag"), target=Target(),
            declaration=Declaration(reversible=reversible, intent=intent),
            params=params))

    @mcp.tool(name="main_mouse_down", description=(
        "Low-level: press and hold the left mouse button at (x,y). Advanced "
        "primitive — only runs at L4 (full autonomy). Auto-released by a watchdog "
        "if never followed by main_mouse_up."))
    def main_mouse_down(x: int, y: int, intent: str, display: int | None = None,
                        space: str = "global", max_width: int = 720,
                        region: dict | None = None) -> dict:
        """Press and hold the mouse button (L4 primitive)."""
        x, y = _resolve_point(x, y, display, space, max_width, region)
        return organ.act(MotorAction(
            name="mouse_down", level=level_for("main_mouse_down"), target=_target(x, y, None, None),
            declaration=Declaration(reversible=True, intent=intent), params={"x": x, "y": y}))

    @mcp.tool(name="main_mouse_up", description="Low-level: release the held left mouse button at (x,y).")
    def main_mouse_up(x: int, y: int, intent: str, display: int | None = None,
                      space: str = "global", max_width: int = 720,
                      region: dict | None = None) -> dict:
        """Release the held mouse button."""
        x, y = _resolve_point(x, y, display, space, max_width, region)
        return organ.act(MotorAction(
            name="mouse_up", level=level_for("main_mouse_up"), target=_target(x, y, None, None),
            declaration=Declaration(reversible=True, intent=intent), params={"x": x, "y": y}))

    @mcp.tool(name="main_key_down", description=(
        "Low-level: press and hold a key. Advanced primitive — L4 only. "
        "Auto-released by a watchdog."))
    def main_key_down(key: str, intent: str, modifiers: list[str] | None = None) -> dict:
        """Press and hold a key (L4 primitive)."""
        return organ.act(MotorAction(
            name="key_down", level=level_for("main_key_down"), target=Target(),
            declaration=Declaration(reversible=True, intent=intent),
            params={"key": key, "modifiers": modifiers or []}))

    @mcp.tool(name="main_key_up", description="Low-level: release a held key.")
    def main_key_up(key: str, intent: str) -> dict:
        """Release a held key."""
        return organ.act(MotorAction(
            name="key_up", level=level_for("main_key_up"), target=Target(),
            declaration=Declaration(reversible=True, intent=intent), params={"key": key}))

    @mcp.tool(
        name="main_ceiling",
        description=(
            "Report the active Hands authorization ceiling and which tools it gates. "
            "Read-only — it never changes the ceiling. Check it before driving so you can "
            "declare up-front what you cannot do rather than being refused mid-flow. Returns "
            "{ceiling, l4_active, levels:{tool:level}, gated_above:[tools above the ceiling]}."
        ),
    )
    def main_ceiling() -> dict:
        """Report the active Hands authorization ceiling and gated tools."""
        from .motor.actions import ceiling_report
        return ceiling_report(organ.current_ceiling())


def build_server() -> FastMCP:
    """Assemble the FastMCP server with every sense and organ registered."""
    config = load_config()
    exclusions = ExclusionFilter(config.exclusions)

    mcp = FastMCP("daimon", instructions=build_server_instructions())

    senses: list[Sense] = [
        Vue(exclusions),
        Touche(exclusions),
    ]
    for sense in senses:
        sense.register(mcp)

    _register_motor(mcp)
    _register_overlay(mcp)

    return mcp


def _record_permission_status() -> None:
    """Best-effort: record this process's (correct-context) TCC grant status so
    the onboarding GUI can confirm the client app actually has the permissions.
    TCC attaches to the launching client, not Daimon.app — only the server,
    running under that client, sees the true status."""
    try:
        from .setup.permissions import MacOSBackend, record_status
        record_status(MacOSBackend())
    except Exception:
        pass  # never block the server on a marker write


def main() -> None:
    """Entry point: record TCC status, then run the stdio server."""
    _record_permission_status()
    build_server().run()  # stdio transport by default


if __name__ == "__main__":
    main()
