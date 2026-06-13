"""Generate the Daimon app icon set (PNGs) for packaging.

Rasterizes the brand vector `build/assets/daimon-app-icon.svg` (the "aperture
eye": a glassy midnight tile with a sentinel-mint iris) at every size macOS
`iconutil` expects, into `build/generated-icons/app-<size>.png`. The build
script then assembles the `.iconset` + `.icns`.

Primary path is `rsvg-convert` (Homebrew `librsvg`) — it renders the gradients
and clip-paths faithfully. If it is absent, falls back to a sober PIL
placeholder so the build never hard-fails on a machine without librsvg.

    python build/make_icon.py [--out build/generated-icons]
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

_SIZES = (16, 32, 64, 128, 256, 512, 1024)
_HERE = Path(__file__).resolve().parent
_APP_SVG = _HERE / "assets" / "daimon-app-icon.svg"

# Placeholder fallback palette (only used when rsvg-convert is unavailable).
_BG = (24, 26, 32)
_FG = (39, 224, 176)     # sentinel mint #27E0B0
_RING = (58, 70, 88)


def _render_svg(svg: Path, size: int, out: Path) -> bool:
    """Rasterize `svg` to a `size`x`size` PNG with rsvg-convert. False if absent."""
    rsvg = shutil.which("rsvg-convert")
    if not rsvg:
        return False
    subprocess.run(
        [rsvg, "-w", str(size), "-h", str(size), str(svg), "-o", str(out)],
        check=True,
    )
    return True


def _draw_placeholder(size: int):
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = max(1, size // 12)
    radius = size // 5
    d.rounded_rectangle([pad, pad, size - pad, size - pad], radius=radius, fill=_BG)
    ring_pad = pad + max(1, size // 10)
    d.ellipse([ring_pad, ring_pad, size - ring_pad, size - ring_pad], outline=_RING,
              width=max(1, size // 64))
    glyph = "δ"
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Georgia.ttf", int(size * 0.5))
    except Exception:
        font = ImageFont.load_default()
    box = d.textbbox((0, 0), glyph, font=font)
    gw, gh = box[2] - box[0], box[3] - box[1]
    d.text(((size - gw) / 2 - box[0], (size - gh) / 2 - box[1]), glyph, font=font, fill=_FG)
    return img


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="build/generated-icons")
    args = p.parse_args(argv)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    used_svg = _APP_SVG.exists() and shutil.which("rsvg-convert") is not None
    if not used_svg:
        print("WARNING: rsvg-convert or brand SVG missing — emitting placeholder δ art.")

    for size in _SIZES:
        dst = out / f"app-{size}.png"
        if used_svg:
            _render_svg(_APP_SVG, size, dst)
        else:
            _draw_placeholder(size).save(dst)

    print(f"icons written to {out} ({'brand SVG' if used_svg else 'placeholder'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
