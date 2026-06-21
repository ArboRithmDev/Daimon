"""Generate / update the release manifest (latest.json) + SHA256SUMS.

Each platform build (Windows on Windows, macOS on Mac) adds ITS asset entry to
the same latest.json — merged by platform key, so the final manifest carries both
once both builds have run. Bumping the version resets the asset set.

Usage:
    python build/make_manifest.py --version 0.0.8 --out dist \
        --platform win64 --asset dist/Daimon-0.0.8-setup.exe [--notes "…"]

The manifest is published to the GitHub release alongside the assets; clients
fetch it from `…/releases/latest/download/latest.json` and verify the SHA256
before applying.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

_DEFAULT_BASE = "https://github.com/ArboRithmDev/Daimon/releases/latest/download"
_CHUNK = 1 << 16


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(_CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def update_manifest(out_dir: Path, version: str, platform: str, asset: Path,
                    *, base_url: str = _DEFAULT_BASE, notes: str = "") -> dict:
    """Merge this platform's asset into latest.json; return the manifest dict."""
    manifest_path = out_dir / "latest.json"
    data = {}
    if manifest_path.exists():
        data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("version") != version:           # version bump → fresh asset set
        data = {"version": version, "notes": notes, "assets": {}}
    if notes:
        data["notes"] = notes
    digest = sha256(asset)
    data.setdefault("assets", {})[platform] = {
        "url": f"{base_url.rstrip('/')}/{asset.name}",
        "sha256": digest,
    }
    manifest_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")

    # SHA256SUMS — keep one line per asset, sorted, updated in place.
    sums_path = out_dir / "SHA256SUMS"
    lines: dict[str, str] = {}
    if sums_path.exists():
        for ln in sums_path.read_text(encoding="utf-8").splitlines():
            if "  " in ln:
                h, name = ln.split("  ", 1)
                lines[name] = h
    lines[asset.name] = digest
    sums_path.write_text("".join(f"{h}  {n}\n" for n, h in sorted(lines.items())),
                         encoding="utf-8")
    return data


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", required=True)
    ap.add_argument("--out", required=True, help="output dir (e.g. dist)")
    ap.add_argument("--platform", required=True, choices=["win64", "macos"])
    ap.add_argument("--asset", required=True, help="path to the built asset")
    ap.add_argument("--base-url", default=_DEFAULT_BASE)
    ap.add_argument("--notes", default="")
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    data = update_manifest(out, args.version, args.platform, Path(args.asset),
                           base_url=args.base_url, notes=args.notes)
    print(f"latest.json updated: {args.platform} -> {data['assets'][args.platform]['url']}")
    print(f"SHA256SUMS: {out / 'SHA256SUMS'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
