"""Pure coordinate-space reprojection — OS-agnostic, no screen access.

This is the deterministic core that kills coord-calibration friction: given a
display's global origin, the snapshot's downscale ratio, and the optional capture
region, it maps image pixels to global pixels and back with no guessing.

A snapshot is taken per display, optionally cropped to a `region`, then
downscaled by `image_scale` so the payload stays small. The reverse chain is
therefore:

    global = display_origin + region_offset + image / image_scale

Negative origins (a display physically to the left of the main one) fall out of
the math for free — the client never has to handle negative global coords itself.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CoordSpace:
    """Everything needed to reproject image pixels to/from global pixels.

    - `display_origin_(x|y)`: the display's top-left in the global desktop space
      (can be negative for a left/above display).
    - `image_scale`: downscale ratio applied to the capture (image_px / source_px);
      1.0 = no downscale. global = origin + region + image / image_scale.
    - `region_(x|y)`: top-left of the captured sub-region within the display
      (0 when the whole display was captured).
    """

    display_origin_x: int
    display_origin_y: int
    image_scale: float
    region_x: int = 0
    region_y: int = 0

    def to_global(self, image_x: float, image_y: float) -> tuple[int, int]:
        """Map a pixel in the snapshot image to its global desktop pixel."""
        gx = self.display_origin_x + self.region_x + image_x / self.image_scale
        gy = self.display_origin_y + self.region_y + image_y / self.image_scale
        return round(gx), round(gy)

    def to_image(self, global_x: float, global_y: float) -> tuple[int, int]:
        """Inverse of `to_global`: global desktop pixel back to image pixel."""
        ix = (global_x - self.display_origin_x - self.region_x) * self.image_scale
        iy = (global_y - self.display_origin_y - self.region_y) * self.image_scale
        return round(ix), round(iy)


def coord_space_from_frame(frame) -> CoordSpace:
    """Build a CoordSpace from a captured Frame (both backends share this)."""
    region = frame.region or {}
    return CoordSpace(
        display_origin_x=frame.display_origin_x,
        display_origin_y=frame.display_origin_y,
        image_scale=frame.image_scale,
        region_x=int(region.get("x", 0)) if region else 0,
        region_y=int(region.get("y", 0)) if region else 0,
    )


def coord_space_contract(frame) -> dict:
    """The JSON-serializable coord-space contract served beside the snapshot image.

    Shape matches cadrage Annexe A:
      {display_index, display_origin:{x,y}, physical_size:{w,h},
       image_size:{w,h}, image_scale, region, dpi}
    """
    return {
        "display_index": frame.display_index,
        "display_origin": {"x": frame.display_origin_x, "y": frame.display_origin_y},
        "physical_size": {"w": frame.physical_width, "h": frame.physical_height},
        "image_size": {"w": frame.width, "h": frame.height},
        "image_scale": frame.image_scale,
        "region": frame.region,
        "dpi": frame.dpi,
    }
