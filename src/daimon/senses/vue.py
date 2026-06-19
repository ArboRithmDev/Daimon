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
import json

from mcp.server.fastmcp import Image as MCPImage
from mcp.types import TextContent

from ..capture import screen
from ..capture.coordspace import CoordSpace, coord_space_contract
from .base import Sense


class Vue(Sense):
    """Read-only sight sense: serves screen pixels, gated and redacted first."""

    name = "vue"

    def register(self, mcp) -> None:
        """Expose the display-list and snapshot tools on the FastMCP server."""
        @mcp.tool(
            name="vue_displays",
            description=(
                "List active displays as [{index, width, height, is_main, "
                "origin:{x,y}, dpi}]. `origin` is the display's global top-left "
                "(negative for a display left of/above the main one); `dpi` is its "
                "effective resolution. Use an index with vue_snapshot to capture "
                "a specific screen, and origin+dpi to reproject coords deterministically."
            ),
        )
        def vue_displays() -> list[dict]:
            return [
                {
                    "index": d.index,
                    "width": d.width,
                    "height": d.height,
                    "is_main": d.is_main,
                    "origin": {"x": d.origin_x, "y": d.origin_y},
                    "dpi": d.dpi,
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
                         region: dict | None = None) -> list:
            frame = screen.capture_display(display_index=display, max_width=max_width, region=region)

            gate = self._exclusions.evaluate_frontmost(frame.frontmost_bundle_id)
            if gate.refused:
                raise PermissionError(f"Vue refused: {gate.reason}")

            image = self._redact(frame)

            buf = io.BytesIO()
            image.save(buf, format="PNG")
            # Two content blocks: the coord-space CONTRACT (so the client never
            # re-derives offset/scale by trial and error) + the image itself.
            contract = {"coord_space": coord_space_contract(frame)}
            return [
                TextContent(type="text", text=json.dumps(contract)),
                MCPImage(data=buf.getvalue(), format="png"),
            ]

        @mcp.tool(
            name="vue_resolve",
            description=(
                "Resolve image pixels (as seen in a vue_snapshot of `display`) to "
                "global desktop pixels, and inverse. Pass image_x/image_y to get "
                "{global_x, global_y}; pass global_x/global_y for {image_x, image_y}. "
                "`max_width`/`region` must match the snapshot they came from. "
                "Use this instead of computing offsets/scale yourself."
            ),
        )
        def vue_resolve(display: int = 0, max_width: int = 720,
                        region: dict | None = None,
                        image_x: float | None = None, image_y: float | None = None,
                        global_x: float | None = None, global_y: float | None = None) -> dict:
            cs = self._coord_space(display, max_width, region)
            if image_x is not None and image_y is not None:
                gx, gy = cs.to_global(image_x, image_y)
                return {"global_x": gx, "global_y": gy}
            if global_x is not None and global_y is not None:
                ix, iy = cs.to_image(global_x, global_y)
                return {"image_x": ix, "image_y": iy}
            raise ValueError("vue_resolve needs either image_x/image_y or global_x/global_y")

    def _redact(self, frame) -> object:
        """Apply the exclusion redaction chain to a captured frame's image.

        Region redaction (declared exclusion rects) then best-effort per-element
        secret blackout. Never fails the capture on a redaction-probe error.
        """
        image = self._exclusions.redact_image(frame.image)
        try:
            rects = self._secret_rects(frame.frontmost_bundle_id)
            from ..exclusions import black_out_rects
            black_out_rects(image, rects)
        except Exception:
            pass  # best-effort; never fail a capture on redaction-probe error
        return image

    def _coord_space(self, display: int, max_width: int,
                     region: dict | None) -> CoordSpace:
        """Build the reprojection coord-space for a display+capture params, no capture.

        Derives the same offset/scale a snapshot would, from display geometry:
        the captured source width is the region width (if any) else the display
        width; the downscale ratio is max_width/source_width when it exceeds it.
        """
        displays = screen.list_displays()
        if display < 0 or display >= len(displays):
            raise IndexError(
                f"display {display} out of range (0..{len(displays) - 1})"
            )
        d = displays[display]
        source_w = int(region["width"]) if region else d.width
        image_scale = max_width / source_w if (max_width and source_w > max_width) else 1.0
        rx = int(region["x"]) if region else 0
        ry = int(region["y"]) if region else 0
        return CoordSpace(
            display_origin_x=d.origin_x,
            display_origin_y=d.origin_y,
            image_scale=image_scale,
            region_x=rx,
            region_y=ry,
        )

    def _secret_rects(self, bundle_id: str | None) -> list[dict]:
        """Return {x,y,width,height} rects for secret-role elements in the frontmost app.

        Best-effort: returns [] whenever accessibility is unavailable or errors.
        The whole-app secret-app gate is already handled by evaluate_frontmost;
        this method handles per-element secret roles only.
        """
        try:
            from ..capture import accessibility as ax
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
