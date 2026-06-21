"""macOS screen capture backend for the Vue sense.

Uses Quartz (CoreGraphics) to grab a display as a PIL image. Requires the host
process to hold Screen Recording permission (System Settings → Privacy &
Security → Screen Recording). Returns raw pixels only — Daimon does no
vision/OCR itself; the AI client looks at the image with its own eyes.

Capture is per-display (CGDisplayCreateImage) so each frame is a single clean
screen, no black padding from a multi-display bounding box.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Display:
    """An active display and its index in the active-display list.

    `origin_x`/`origin_y` place the display's top-left in the global desktop
    space (negative for a display left of / above the main one); `dpi` is the
    effective dots-per-inch. Together they make image→global mapping deterministic.

    `stable_id` is an OS-native, persistent identity for the physical panel
    (empty when the platform has none). macOS leaves it empty and identifies an
    environment by geometry alone; Windows fills it from the CCD monitor device
    path (EDID-derived), so a saved calibration profile re-matches the same
    physical monitors even after a resolution, DPI or port change reshuffles the
    geometry. `calibration.environment_signature` folds it in when present.
    """

    index: int
    display_id: int
    width: int
    height: int
    is_main: bool
    origin_x: int = 0
    origin_y: int = 0
    dpi: int = 96
    stable_id: str = ""


@dataclass(frozen=True)
class Frame:
    """A captured screen frame plus the metadata a sense needs to describe it.

    The coord-space fields make reprojection deterministic (see
    `capture.coordspace`): `display_origin_*` is the source display's global
    top-left, `physical_*` is the source (pre-downscale, pre-crop) display size,
    `width`/`height` is the served image size, `image_scale` is the downscale
    ratio (image_px / source_px), and `region` is the captured sub-region (or None).
    """

    image: "object"  # PIL.Image.Image (typed loosely to avoid a hard import here)
    width: int
    height: int
    display_index: int
    frontmost_bundle_id: str | None
    display_origin_x: int = 0
    display_origin_y: int = 0
    physical_width: int = 0
    physical_height: int = 0
    image_scale: float = 1.0
    region: dict | None = None
    dpi: int = 96


def frontmost_bundle_id() -> str | None:
    """Bundle id of the frontmost application, for the app-level exclusion gate."""
    from AppKit import NSWorkspace

    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return app.bundleIdentifier() if app else None


def list_displays() -> list[Display]:
    """Enumerate active displays in stable order (index 0 = first active)."""
    import Quartz

    max_displays = 16
    err, ids, count = Quartz.CGGetActiveDisplayList(max_displays, None, None)
    if err != 0:
        raise RuntimeError(f"CGGetActiveDisplayList failed: {err}")

    main_id = Quartz.CGMainDisplayID()
    out: list[Display] = []
    for i, did in enumerate(ids[:count]):
        ox, oy = _display_origin(did)
        out.append(
            Display(
                index=i,
                display_id=int(did),
                width=int(Quartz.CGDisplayPixelsWide(did)),
                height=int(Quartz.CGDisplayPixelsHigh(did)),
                is_main=(did == main_id),
                origin_x=ox,
                origin_y=oy,
                dpi=_display_dpi(did),
            )
        )
    return out


def _display_origin(did) -> tuple[int, int]:
    """Global top-left of a display, via CGDisplayBounds(did).origin."""
    import Quartz

    bounds = Quartz.CGDisplayBounds(did)
    return int(bounds.origin.x), int(bounds.origin.y)


def _display_dpi(did) -> int:
    """Effective DPI from the display mode's pixel width over its physical size.

    Quartz reports physical size in millimetres; dpi = pixels / (mm / 25.4).
    Falls back to the 96 baseline when the physical size is unknown (0).
    """
    import Quartz

    try:
        mode = Quartz.CGDisplayCopyDisplayMode(did)
        px_w = Quartz.CGDisplayModeGetPixelWidth(mode) if mode else 0
        size_mm = Quartz.CGDisplayScreenSize(did)  # CGSize in millimetres
        width_mm = float(size_mm.width)
        if px_w and width_mm > 0:
            return int(round(px_w / (width_mm / 25.4)))
    except Exception:
        pass
    return 96


def _cgimage_to_pil(image_ref):
    """Convert a CGImage (BGRA) to an RGB PIL image."""
    import Quartz
    from PIL import Image

    width = Quartz.CGImageGetWidth(image_ref)
    height = Quartz.CGImageGetHeight(image_ref)
    bytes_per_row = Quartz.CGImageGetBytesPerRow(image_ref)

    provider = Quartz.CGImageGetDataProvider(image_ref)
    buf = bytes(Quartz.CGDataProviderCopyData(provider))

    img = Image.frombuffer("RGBA", (width, height), buf, "raw", "BGRA", bytes_per_row, 1)
    return img.convert("RGB")


def crop_region(image, region: dict | None):
    """Crop a PIL image to {x,y,width,height}, clamped to the image. Pure."""
    if not region:
        return image
    x = max(0, int(region["x"])); y = max(0, int(region["y"]))
    right = min(image.width, x + int(region["width"]))
    bottom = min(image.height, y + int(region["height"]))
    return image.crop((x, y, right, bottom))


def capture_display(display_index: int = 0, max_width: int | None = 720,
                    region: dict | None = None) -> Frame:
    """Capture one active display by index, optionally downscaled to `max_width`.

    `display_index` indexes `list_displays()`; 0 is the first active display.
    `region` is an optional {x, y, width, height} dict to capture a sub-region;
    cropping happens before downscaling.
    Downscaling keeps payloads small for the ~1-2 fps ambient use case and
    spares the client's vision budget.
    """
    import Quartz

    displays = list_displays()
    if not displays:
        raise RuntimeError("No active displays found.")
    if display_index < 0 or display_index >= len(displays):
        raise IndexError(
            f"display_index {display_index} out of range (0..{len(displays) - 1})"
        )

    display = displays[display_index]
    image_ref = Quartz.CGDisplayCreateImage(display.display_id)
    if image_ref is None:
        raise RuntimeError(
            "Screen capture returned no image — check Screen Recording permission."
        )

    img = _cgimage_to_pil(image_ref)
    physical_width, physical_height = img.width, img.height
    img = crop_region(img, region)
    image_scale = 1.0
    if max_width and img.width > max_width:
        image_scale = max_width / img.width
        img = img.resize((max_width, int(img.height * image_scale)))

    return Frame(
        image=img,
        width=img.width,
        height=img.height,
        display_index=display_index,
        frontmost_bundle_id=frontmost_bundle_id(),
        display_origin_x=display.origin_x,
        display_origin_y=display.origin_y,
        physical_width=physical_width,
        physical_height=physical_height,
        image_scale=image_scale,
        region=region,
        dpi=display.dpi,
    )


# Back-compat alias: the main display is index 0 in practice for single-screen
# setups; callers wanting "the primary" can pass the main display's index.
def capture_main_display(max_width: int | None = 1600) -> Frame:
    """Capture the primary display, falling back to index 0 if none is flagged main."""
    main = next((d for d in list_displays() if d.is_main), None)
    return capture_display(main.index if main else 0, max_width=max_width)
