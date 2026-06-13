# macOS DMG build — Daimon

Build, sign, and notarize the Daimon macOS DMG on a Mac. Adapted from the
SecondBrain Desktop pipeline; Daimon is a single self-contained package, so
there is no separate engine / offline-wheels staging.

## What the `.app` is

`Daimon.app` is the **onboarding launcher**. Double-clicking it runs the
windowed setup GUI, which registers Daimon into detected AI clients and guides
the macOS permission grants. The bundle ships **two** executables:

| Executable | Role |
|-----------|------|
| `Daimon` (`CFBundleExecutable`) | the onboarding GUI a user double-clicks |
| `Contents/MacOS/daimon` | the MCP stdio server / CLI — what AI clients launch |

`invocation.py` registers clients against `…/Daimon.app/Contents/MacOS/daimon`
once the app is in `/Applications`.

## Prerequisites

1. **Xcode Command Line Tools**: `xcode-select --install` (provides `codesign`,
   `iconutil`, `hdiutil`, `xcrun`, `notarytool`).
2. **Python 3.12+**.
3. **Developer ID Application certificate** in the login keychain (Apple
   Developer Program, 99 USD/yr). Verify:
   ```bash
   security find-identity -p codesigning -v   # → "Developer ID Application: <Name> (TEAMID)"
   ```
4. **Notary credentials**:
   ```bash
   xcrun notarytool store-credentials AC_PASSWORD \
     --apple-id you@example.com --team-id TEAMID --password app-specific-password
   ```

## Build

```bash
export DEV_ID="Developer ID Application: <Name> (TEAMID)"
export TEAM_ID="TEAMID"
cd /Users/Ben/Projets/Daimon
./build/macos/build_macos.sh                 # signed + notarized
```

The script: builds `.venv-build`, installs `daimon[build]` (PyInstaller),
generates a placeholder icon set + `.icns`, runs PyInstaller against
`build/daimon.spec` → `dist/Daimon.app`, signs the inner Mach-O + frameworks +
the `.app` (hardened runtime), wraps it in a DMG (`hdiutil` + `Applications`
symlink), signs the DMG, then notarizes + staples.

Artifact: `dist/Daimon-<version>.dmg`.

### Escape hatches

```bash
./build/macos/build_macos.sh --no-notarize   # sign, skip notarization
./build/macos/build_macos.sh --no-sign       # local-only DMG (no cert needed)
```

Use `--no-sign` for fast iteration on the same Mac. Never distribute an
unsigned DMG — Gatekeeper refuses it elsewhere.

## Verify

```bash
DMG="dist/Daimon-<version>.dmg"
codesign --verify --deep --strict --verbose=2 "$DMG"
spctl --assess --type install --verbose=2 "$DMG"
stapler validate "$DMG"
hdiutil attach "$DMG" && open "/Volumes/Daimon "*/Daimon.app
```

## Permissions (TCC) note — important

macOS TCC permissions (Screen Recording, Accessibility) attach to the
**responsible parent GUI** that launches `daimon` — the AI client (Terminal,
Ghostty, Claude, VS Code…) — **not** to `Daimon.app`. So:

- The onboarding GUI guides the user to grant the permissions to **their AI
  client app**, and opens the right Settings pane.
- It cannot verify the client's grant from its own process. Instead, the
  **server self-reports**: on startup `daimon` writes its real (correct-context)
  grant status to `~/Library/Application Support/Daimon/permissions.json`; the
  onboarding GUI reads it to confirm "your AI has the permissions ✅". If the
  marker is missing, the user is told to launch their AI once.

## Publish

```bash
gh release upload daimon-v<version> dist/Daimon-<version>.dmg --clobber
```

## Replace the placeholder icon

`build/make_icon.py` draws a placeholder glyph. Before a public release, replace
its output (or drop final `app-<size>.png` art into `build/generated-icons/`)
with the real brand icon, then rebuild.
