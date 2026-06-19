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
from ..exclusions import ExclusionFilter
from .base import Sense
from .calibration import (
    active_profile_brief,
    coord_space_from_profile,
    profile_from_displays,
)
from .find import locate, rank_matches


class Vue(Sense):
    """Read-only sight sense: serves screen pixels, gated and redacted first.

    Holds a calibration profile store (AXE 2): the active environment's topology
    can be captured once under a named profile and auto-matched at boot, so coord
    resolution reads per-display offset/scale from the saved profile instead of
    re-probing the screen on every call.
    """

    name = "vue"

    def __init__(self, exclusions: ExclusionFilter, profile_store=None,
                 ocr=None) -> None:
        super().__init__(exclusions)
        if profile_store is None:
            from .calibration_store import ProfileStore
            profile_store = ProfileStore()
        self._profiles = profile_store
        # OCR backend for vue_find (AXE 3) is INJECTED: real Apple Vision on
        # macOS, a parity scaffold on Windows, a Fake in tests. Resolved lazily
        # so importing Vue never pulls the OCR framework.
        if ocr is None:
            from .find_ocr import default_ocr
            ocr = default_ocr()
        self._ocr = ocr

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
                "`source` selects the geometry: 'probe' (default, live displays) "
                "or 'profile' (the auto-matched calibration profile; falls back to "
                "probe if no profile matches). "
                "Use this instead of computing offsets/scale yourself."
            ),
        )
        def vue_resolve(display: int = 0, max_width: int = 720,
                        region: dict | None = None,
                        image_x: float | None = None, image_y: float | None = None,
                        global_x: float | None = None, global_y: float | None = None,
                        source: str = "probe") -> dict:
            cs = self._coord_space(display, max_width, region, source=source)
            if image_x is not None and image_y is not None:
                gx, gy = cs.to_global(image_x, image_y)
                return {"global_x": gx, "global_y": gy}
            if global_x is not None and global_y is not None:
                ix, iy = cs.to_image(global_x, global_y)
                return {"image_x": ix, "image_y": iy}
            raise ValueError("vue_resolve needs either image_x/image_y or global_x/global_y")

        @mcp.tool(
            name="vue_find",
            description=(
                "Vue-only fallback: locate a VISIBLE text label on `display` by OCR "
                "and return CLICKABLE global coords (already reprojected via the "
                "coord-space — no manual offset/scale, negative displays handled). "
                "Use this when touche_tree/touche_probe go mute (WinDev, old Win32, "
                "custom-drawn, Electron: summary 'None'/generic PaneControl) so there "
                "is no accessibility tree to click. Returns {found, text, score, "
                "image_x/y, global_x/y, candidates}. Feed global_x/global_y straight "
                "to main_click (default space='global'). `max_width`/`region` must "
                "match the snapshot geometry you intend to act in. This is a LOCATOR "
                "(returns a position), not an interpreter: localisation != "
                "interpretation — a scoped, on-device / no-network exception to "
                "Daimon doing no vision. Daimon still does not read the screen FOR you."
            ),
        )
        def vue_find(text: str, display: int = 0, max_width: int = 720,
                     region: dict | None = None, min_score: float = 0.6,
                     source: str = "probe") -> dict:
            if not text or not text.strip():
                raise ValueError("vue_find needs a non-empty text to locate")
            frame = screen.capture_display(
                display_index=display, max_width=max_width, region=region)

            gate = self._exclusions.evaluate_frontmost(frame.frontmost_bundle_id)
            if gate.refused:
                raise PermissionError(f"Vue refused: {gate.reason}")

            image = self._redact(frame)
            words = self._ocr.recognize(image)
            cs = self._coord_space(display, max_width, region, source=source)

            hit = locate(words, text, cs, min_score=min_score)
            if hit is not None:
                return {"found": True, "candidates": [], **hit}
            # Miss: surface what WAS on screen (best-effort, low threshold) so the
            # pilot can retry with the exact label rather than guess blindly.
            near = rank_matches(words, text, min_score=0.0)[:5]
            return {
                "found": False,
                "text": None,
                "score": None,
                "image_x": None,
                "image_y": None,
                "global_x": None,
                "global_y": None,
                "candidates": [m.word.text for m in near],
            }

        @mcp.tool(
            name="vue_calibrate",
            description=(
                "Capture the full screen topology (per-display origin, size, dpi, "
                "arrangement) and persist it under a named calibration profile "
                "(e.g. 'bureau-3-ecrans', 'portable-seul', 'teletravail-ultralarge'). "
                "Recapturing the same name replaces it (idempotent). The saved "
                "profile is auto-matched at boot by a deterministic signature, so "
                "coord resolution is read from it instead of being re-probed."
            ),
        )
        def vue_calibrate(name: str) -> dict:
            if not name or not name.strip():
                raise ValueError("vue_calibrate needs a non-empty profile name")
            name = name.strip()
            displays = screen.list_displays()
            profile = profile_from_displays(name, displays)
            self._profiles.save(profile)
            return {
                "saved": True,
                "name": name,
                "signature": profile.signature,
                "display_count": len(profile.displays),
                "displays": [d.to_dict() for d in profile.displays],
            }

        @mcp.tool(
            name="vue_profile",
            description=(
                "Report the calibration profile auto-matched to the current screen "
                "topology (by signature). If the environment is unknown, signals it "
                "and proposes calibrating one with vue_calibrate. Lists the known "
                "profile names either way."
            ),
        )
        def vue_profile() -> dict:
            displays = screen.list_displays()
            matched = self._profiles.match(displays)
            known = [p.name for p in self._profiles.load_all()]
            if matched is not None:
                return {
                    "matched": True,
                    "active_profile": matched.name,
                    "signature": matched.signature,
                    "display_count": len(matched.displays),
                    "known_profiles": known,
                }
            from .calibration import environment_signature
            return {
                "matched": False,
                "active_profile": None,
                "signature": environment_signature(displays),
                "known_profiles": known,
                "hint": (
                    "Unknown environment — no saved profile matches this topology. "
                    "Call vue_calibrate(name=...) to create one."
                ),
            }

        @mcp.tool(
            name="vue_profile_brief",
            description=(
                "Boot brief for a DELEGATED sub-agent (AXE 5). An orchestrator hands "
                "a small fast model only a profile name via `expected`; this confirms "
                "that name is the one auto-matched to the live screen topology and "
                "returns the addressable display indices, so the sub-agent drives the "
                "UI mechanically with no geometric reasoning. Returns {matched, "
                "active_profile, signature, expected_ok, displays:[{index, width, "
                "height, is_main, origin_x, origin_y, dpi}]}. GO only if expected_ok "
                "is True; otherwise the environment doesn't match the handed-down "
                "profile — abort and report rather than drive blind."
            ),
        )
        def vue_profile_brief(expected: str | None = None) -> dict:
            displays = screen.list_displays()
            return active_profile_brief(self._profiles, displays, expected=expected)

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
                     region: dict | None, source: str = "probe") -> CoordSpace:
        """Build the reprojection coord-space for a display+capture params, no capture.

        Derives the same offset/scale a snapshot would, from display geometry:
        the captured source width is the region width (if any) else the display
        width; the downscale ratio is max_width/source_width when it exceeds it.

        With `source="profile"` the geometry is read from the auto-matched
        calibration profile (AXE 2) rather than a live probe — falling back to
        probing when no profile matches the current environment.
        """
        if source == "profile":
            displays = screen.list_displays()
            matched = self._profiles.match(displays)
            if matched is not None:
                return coord_space_from_profile(matched, display, max_width, region)
            # no matching profile: fall through to live probing
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
