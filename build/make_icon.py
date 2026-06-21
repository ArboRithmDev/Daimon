"""Generate the Daimon app icon set (PNGs) for packaging.

Rasterizes the brand vector `build/assets/daimon-app-icon.svg` (the "Duo": a
presence-purple lobe with its companion-amber lobe beside it, on an indigo
midnight tile) at every size macOS `iconutil` expects, into
`build/generated-icons/app-<size>.png`. The build script then assembles the
`.iconset` + `.icns`.

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
_BG = (30, 38, 96)       # indigo tile #1e2660
_FG = (182, 108, 255)    # presence purple #B66CFF
_RING = (232, 178, 58)   # companion amber #E8B23A


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


# --- Windows .ico path ------------------------------------------------------
# Windows has no librsvg/iconutil. PySide6's QtSvg (already a runtime dep) renders
# the brand vector crisply at each size; Pillow assembles the multi-resolution
# .ico that daimon_win.spec embeds as the exe/installer icon. No new dependency.

_ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)


def _render_svg_qt(svg: Path, size: int):
    """Rasterize `svg` to a `size`x`size` RGBA PIL image via QtSvg. None on failure."""
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from io import BytesIO

    from PIL import Image
    from PySide6.QtCore import QBuffer, QByteArray, Qt
    from PySide6.QtGui import QGuiApplication, QImage, QPainter
    from PySide6.QtSvg import QSvgRenderer

    if QGuiApplication.instance() is None:
        QGuiApplication([])  # offscreen; required before any QImage/QPainter use
    renderer = QSvgRenderer(str(svg))
    if not renderer.isValid():
        return None
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    painter = QPainter(img)
    renderer.render(painter)
    painter.end()
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QBuffer.WriteOnly)
    img.save(buf, "PNG")
    buf.close()
    return Image.open(BytesIO(bytes(ba))).convert("RGBA")


def write_ico(out: Path) -> bool:
    """Write a multi-resolution `Daimon.ico` from the brand app SVG. False if the
    SVG or QtSvg is unavailable (build falls back to a placeholder-free, iconless
    exe rather than hard-failing)."""
    if not _APP_SVG.exists():
        return False
    try:
        frames = [im for s in _ICO_SIZES if (im := _render_svg_qt(_APP_SVG, s))]
    except Exception as exc:  # noqa: BLE001 — best-effort build helper
        print(f"WARNING: QtSvg .ico render failed ({exc}); skipping icon.")
        return False
    if not frames:
        return False
    out.parent.mkdir(parents=True, exist_ok=True)
    base = frames[-1]  # largest; Pillow embeds the rest as additional ICO frames
    base.save(out, format="ICO", sizes=[(im.width, im.height) for im in frames],
              append_images=frames[:-1])
    print(f"icon written to {out} ({len(frames)} sizes)")
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
    p.add_argument("--ico", metavar="PATH",
                   help="emit a multi-resolution Windows .ico (QtSvg) and exit")
    args = p.parse_args(argv)

    # Windows packaging path: a single .ico for the exe/installer icon.
    if args.ico:
        return 0 if write_ico(Path(args.ico)) else 1

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
