"""Vue — sense #1. The eye.

Exposes MCP tools to look at the screen:

  - vue_displays  : list the active displays (so the client can choose one).
  - vue_snapshot  : capture a display and return it as an image.

The exclusion filter runs first: if an excluded app is frontmost the snapshot
is refused; otherwise fixed exclusion regions are blacked out before the image
leaves the process.

Daimon supplies pixels only. It performs no vision/OCR — the calling AI reads
the image with its own eyes. That is what keeps Daimon agnostic.
"""

from __future__ import annotations

import io

from mcp.server.fastmcp import Image as MCPImage

from .. import backends
from .base import Sense


class Vue(Sense):
    """Read-only sight sense: serves screen pixels, gated and redacted first."""

    name = "vue"

    def register(self, mcp) -> None:
        """Expose the display-list and snapshot tools on the FastMCP server."""
        @mcp.tool(
            name="vue_displays",
            description=(
                "List active displays as [{index, width, height, is_main}]. "
                "Use an index with vue_snapshot to capture a specific screen."
            ),
        )
        def vue_displays() -> list[dict]:
            screen = backends.build_screen()
            return [
                {
                    "index": d.index,
                    "width": d.width,
                    "height": d.height,
                    "is_main": d.is_main,
                }
                for d in screen.list_displays()
            ]

        @mcp.tool(
            name="vue_snapshot",
            description=(
                "Capture one macOS display and return it as an image. Read-only "
                "ambient perception. `display` indexes vue_displays (default 0). "
                "Default max_width is 720; pass a larger value for fine detail. "
                "`region={x,y,width,height}` restricts capture to a sub-region "
                "(pixel coords, clamped to display bounds). "
                "Excluded apps/regions are filtered out before the image is "
                "returned. Daimon does not interpret the image; look at it yourself."
            ),
        )
        def vue_snapshot(display: int = 0, max_width: int = 720,
                         region: dict | None = None) -> MCPImage:
            screen = backends.build_screen()
            frame = screen.capture_display(display_index=display, max_width=max_width, region=region)

            gate = self._exclusions.evaluate_frontmost(frame.frontmost_bundle_id)
            if gate.refused:
                raise PermissionError(f"Vue refused: {gate.reason}")

            image = self._exclusions.redact_image(frame.image)
            try:
                rects = self._secret_rects(frame.frontmost_bundle_id)
                from ..exclusions import black_out_rects
                black_out_rects(image, rects)
            except Exception:
                pass  # best-effort; never fail a capture on redaction-probe error

            buf = io.BytesIO()
            image.save(buf, format="PNG")
            return MCPImage(data=buf.getvalue(), format="png")

    def _secret_rects(self, bundle_id: str | None) -> list[dict]:
        """Return {x,y,width,height} rects for secret-role elements in the frontmost app.

        Best-effort: returns [] whenever accessibility is unavailable or errors.
        The whole-app secret-app gate is already handled by evaluate_frontmost;
        this method handles per-element secret roles only.
        """
        try:
            ax = backends.build_a11y()
            if not ax.is_trusted():
                return []
            tree = ax.snapshot_tree(max_depth=12, prune_empty=False)
            rects: list[dict] = []

            def walk(node: dict) -> None:
                if not isinstance(node, dict):
                    return
                role = node.get("role")
                if role and self._exclusions.is_target_secret(role=role):
                    pos = node.get("position")
                    size = node.get("size")
                    if pos and size:
                        rects.append({
                            "x": pos["x"],
                            "y": pos["y"],
                            "width": size["width"],
                            "height": size["height"],
                        })
                for child in node.get("children") or []:
                    walk(child)

            walk(tree)
            return rects
        except Exception:
            return []
