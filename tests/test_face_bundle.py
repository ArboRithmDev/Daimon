"""Smoke test for the offline 'face' web bundle. Verifies the build produces a
local, CSP-locked panel with no rogue remote origins. The real network control is
the CSP (default-src 'self'); this gate is defense-in-depth against a CDN/script
or fetch('https://...') leaking into OUR code. Vendored React embeds two known
NON-fetching reference strings (XML namespaces, the prod error-decoder help link)
which CSP would block anyway — those are allowlisted."""

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "src/daimon/face/web"
DIST = WEB / "dist"

# Non-fetching reference strings baked into vendored React. Not remote origins we
# ever connect to; CSP 'self' blocks navigation/fetch regardless.
_ALLOWED_HOSTS = ("www.w3.org", "reactjs.org")
_URL = re.compile(r"https?://([^\"'`)\s]+)")

pytestmark = pytest.mark.skipif(
    not (WEB / "node_modules" / "react").exists(),
    reason="face web deps not vendored (run: cd src/daimon/face/web && npm install)",
)


def _build():
    subprocess.run([sys.executable, str(ROOT / "build/make_face.py")], check=True, cwd=ROOT)


def test_panel_bundle_builds_local_and_csp_locked():
    _build()
    panel = DIST / "panel" / "index.html"
    assert panel.exists(), "panel index.html missing"
    html = panel.read_text()
    assert "default-src 'self'" in html, "CSP missing from panel index.html"
    assert 'src="./bundle.js"' in html, "panel must load only its local bundle"


def test_no_rogue_remote_origin_in_dist():
    _build()
    offenders = []
    for f in DIST.rglob("*"):
        if f.suffix in {".html", ".js", ".css"}:
            for host in _URL.findall(f.read_text()):
                if not host.startswith(_ALLOWED_HOSTS):
                    offenders.append((f.name, host[:60]))
    assert not offenders, f"unexpected remote origin(s) in the bundle: {offenders[:5]}"
