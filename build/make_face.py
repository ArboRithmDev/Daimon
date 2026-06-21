"""Build the offline Daimon 'face' web bundle with esbuild (via npx).

Bundles each surface entry (panel / overlay / onboarding) with vendored React —
no CDN, no remote — and injects a strict CSP into each generated index.html.
Output: src/daimon/face/web/dist/<surface>/{index.html,bundle.js}.

One-time setup (vendors React into web/node_modules):
    cd src/daimon/face/web && npm install

Then:
    python build/make_face.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WEB = ROOT / "src/daimon/face/web"
SRC = WEB / "src"
DIST = WEB / "dist"
SURFACES = ("panel", "overlay", "onboarding")
# default-src 'self' keeps the bundle offline (no remote origin). script-src adds
# 'unsafe-eval' because pywebview builds its window.pywebview.api bridge via
# Function/eval; bounded — the content is our own local bundle, never remote.
CSP = ("default-src 'self'; script-src 'self' 'unsafe-eval'; "
       "style-src 'self' 'unsafe-inline'; img-src 'self' data:;")

_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{csp}">
<style>{css}</style></head>
<body><div id="root"></div>
<script src="./bundle.js"></script></body></html>
"""


def _esbuild(entry: Path, outfile: Path) -> None:
    # Production build: NODE_ENV=production strips React's dev warnings (and the
    # reactjs.org doc URLs they embed); --minify shrinks the offline bundle.
    subprocess.run(
        ["npx", "--yes", "esbuild", str(entry), "--bundle", "--format=iife",
         "--jsx=automatic", "--minify", "--define:process.env.NODE_ENV=\"production\"",
         f"--outfile={outfile}"],
        check=True, cwd=WEB,
    )


def _ensure_deps() -> bool:
    """Vendor React into web/node_modules if missing. Returns False if Node absent."""
    if shutil.which("npm") is None or shutil.which("npx") is None:
        print("ERROR: Node.js (npm/npx) is required to build the face bundle.", file=sys.stderr)
        return False
    if not (WEB / "node_modules" / "react").exists():
        print("==> Vendoring face web deps (npm install)…")
        subprocess.run(["npm", "install", "--no-audit", "--no-fund"], check=True, cwd=WEB)
    return True


def main() -> int:
    if not _ensure_deps():
        return 2

    base_css = (SRC / "base.css").read_text() if (SRC / "base.css").exists() else ""
    built = []
    for surface in SURFACES:
        entry = SRC / surface / "index.jsx"
        if not entry.exists():
            continue
        out_dir = DIST / surface
        out_dir.mkdir(parents=True, exist_ok=True)
        _esbuild(entry, out_dir / "bundle.js")
        (out_dir / "index.html").write_text(_HTML.format(csp=CSP, css=base_css))
        built.append(surface)
    print(f"face bundle -> {DIST}  ({', '.join(built) or 'no surfaces'})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
