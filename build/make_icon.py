"""Generate a placeholder Daimon app icon set (PNGs) for packaging.

PLACEHOLDER ART — replace with the final brand icon before a public release.
Draws a sober premium glyph (a soft-cornered tile with a "δ") at every size
macOS `iconutil` expects, into `build/generated-icons/app-<size>.png`. The
build script then assembles the `.iconset` + `.icns`.

    python build/make_icon.py [--out build/generated-icons]
"""

from __future__ import annotations

import argparse
from pathlib import Path

_SIZES = (16, 32, 64, 128, 256, 512, 1024)
_BG = (24, 26, 32)       # near-black premium
_FG = (120, 150, 255)    # daimon blue
_RING = (60, 66, 84)


def _draw(size: int):
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = max(1, size // 12)
    radius = size // 5
    d.rounded_rectangle([pad, pad, size - pad, size - pad], radius=radius, fill=_BG)
    # subtle ring
    ring_pad = pad + max(1, size // 10)
    d.ellipse([ring_pad, ring_pad, size - ring_pad, size - ring_pad], outline=_RING,
              width=max(1, size // 64))
    # glyph
    glyph = "δ"  # δ
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
    for size in _SIZES:
        _draw(size).save(out / f"app-{size}.png")
    print(f"icons written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
