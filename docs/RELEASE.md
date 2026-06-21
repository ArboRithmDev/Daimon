# Daimon release runbook — v0.0.10 (and beyond)

Authoritative checklist for cutting a public, auto-update-capable Daimon release
for **macOS + Windows**. Phases A–C (integration, parity, plumbing) are already
landed on `main`; this file covers the outward, irreversible **Phase D** that Ben
operates on real machines with signing credentials.

## Release identity (do not drift)

- **Git tag / GitHub release:** `daimon-v0.0.10` (matches `build_macos.sh`'s
  publish hint and the per-asset URLs).
- **Version source of truth:** `pyproject.toml` `[project] version` only. Never
  hardcode a version literal elsewhere (`tests/test_version.py` enforces this).
- **The release MUST be the repository's `latest` GitHub release and MUST NOT be
  flagged "pre-release."** GitHub's `/releases/latest/` endpoint — which the
  updater's `manifest_url` depends on — skips pre-releases. A pre-release would
  silently break auto-update for every installed client.
  - `manifest_url` (see `config/update.example.yaml`):
    `https://github.com/ArboRithmDev/Daimon/releases/latest/download/latest.json`
  - Asset URLs in `latest.json` use the stable
    `…/releases/latest/download/<name>` form (resolved by `build/make_manifest.py`).
- **Manifest platform keys are exactly `macos` and `win64`** — never `macos64`.

## Required release assets (exact filenames)

| Asset                       | Produced by                     | Platform key |
|-----------------------------|---------------------------------|--------------|
| `Daimon-0.0.10.dmg`         | `build/macos/build_macos.sh`    | `macos`      |
| `Daimon-0.0.10-setup.exe`   | `build/windows/build_windows.ps1` | `win64`    |
| `latest.json`               | `make_manifest.py` (both builds) | merged      |
| `SHA256SUMS`                | `make_manifest.py` (both builds) | merged      |

`latest.json` is **per-platform-merged**: each platform's build appends its entry
into the same file. Build one platform, copy its `dist/latest.json` to the second
machine's `dist/` before running that build (or re-run `make_manifest.py` against
it), so the final manifest carries BOTH `assets.macos` and `assets.win64` before
upload.

---

## Phase D — build, sign, publish (BEN-OPERATED, irreversible)

### D1 — Push the integrated `main`

```bash
git log --oneline origin/main..main   # confirm the integration looks right
git push origin main
```

### D2 — Tag the release

```bash
git tag -a daimon-v0.0.10 -m "Daimon 0.0.10 — cross-platform public beta"
git push origin daimon-v0.0.10
```

### D3 — macOS build + notarize (on Ben's Mac)

Requires: Developer ID Application cert (`Benjamin DUBOIS (M729622MH3)`) in the
login keychain; `AC_PASSWORD` notarytool keychain profile; `librsvg`
(`brew install librsvg`).

```bash
./build/macos/build_macos.sh
# Verify:
codesign --verify --deep --strict --verbose=2 dist/Daimon-0.0.10.dmg \
  && spctl --assess --type install -v dist/Daimon-0.0.10.dmg \
  && stapler validate dist/Daimon-0.0.10.dmg
# Produces: dist/Daimon-0.0.10.dmg, dist/latest.json (macos entry), dist/SHA256SUMS
```

### D4 — Windows build + sign (on Ben's Windows host)

Requires: Authenticode cert in the Windows store; Inno Setup 6. Build from `main`
(now cross-platform). Copy the Mac's `dist/latest.json` into `dist/` first so the
win64 entry merges into the SAME manifest.

```powershell
$env:DAIMON_CERT_SUBJECT = "Arborithm"
.\build\windows\build_windows.ps1
# Produces: dist\Daimon-0.0.10-setup.exe, dist\latest.json (now macos+win64), dist\SHA256SUMS
```

### D5 — Create the GitHub release as **latest** (not pre-release)

```bash
gh release create daimon-v0.0.10 \
  dist/Daimon-0.0.10.dmg \
  dist/Daimon-0.0.10-setup.exe \
  dist/latest.json \
  dist/SHA256SUMS \
  --title "Daimon 0.0.10" \
  --notes-file docs/RELEASE.md \
  --latest
```

⚠️ **Do NOT pass `--prerelease`.** Confirm the uploaded `latest.json` carries both
`assets.macos` and `assets.win64` before announcing.

### D6 — Field validation (real machines)

- **macOS auto-focus:** against the freshly installed `Daimon.app`, drive one
  `main_click(ensure_focus=true)` on a background window → expect
  `focus == "activated_and_frontmost"`.
- **Auto-update end-to-end (both OSes):** install 0.0.10, confirm the tray's
  background check fetches `latest.json`, shows "⬆ Update to v…", and a future
  bump applies (download → SHA256 gate → `apply_macos`/`apply_win` swap →
  relaunch). Confirm `apply_macos` replaces `/Applications/Daimon.app` with no
  stale mount.
- Smoke window ops, OCR (`vue_find`, macOS), and the L4 tray on both platforms.
