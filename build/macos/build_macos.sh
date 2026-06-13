#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Build the macOS Daimon.app bundle and a signed + notarized DMG.
#
# Adapted from the SecondBrain Desktop pipeline. Daimon is a single self-
# contained package (no separate engine / offline wheels), so the staging step
# is gone. The .app ships TWO executables:
#   * Daimon  (CFBundleExecutable) — the onboarding GUI a user double-clicks
#   * daimon  (Contents/MacOS/daimon) — the MCP stdio server / CLI dispatcher
#
# Run on a Mac with:
#   * Xcode CLT (codesign, iconutil, hdiutil, xcrun, notarytool)
#   * A Developer ID Application certificate in the login keychain
#   * notarytool credentials in keychain item "AC_PASSWORD":
#       xcrun notarytool store-credentials AC_PASSWORD \
#         --apple-id you@example.com --team-id TEAMID --password app-specific-pw
#
# Usage:
#   ./build/macos/build_macos.sh [--no-notarize] [--no-sign]
# -----------------------------------------------------------------------------
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DIST_DIR="$REPO_ROOT/dist"
BUILD_DIR="$REPO_ROOT/build"
ICONS_DIR="$BUILD_DIR/generated-icons"
VENV_DIR="$REPO_ROOT/.venv-build"
DMG_ROOT="$DIST_DIR/dmg-root"

DEV_ID="${DEV_ID:-Developer ID Application: CHANGEME (TEAMID)}"
TEAM_ID="${TEAM_ID:-TEAMID}"
BUNDLE_ID="${DAIMON_BUNDLE_ID:-fr.arborithm.daimon}"
APP_NAME="Daimon"
APP_BUNDLE="$DIST_DIR/${APP_NAME}.app"

DO_SIGN=1
DO_NOTARIZE=1
for arg in "$@"; do
    case "$arg" in
        --no-sign)     DO_SIGN=0 ;;
        --no-notarize) DO_NOTARIZE=0 ;;
        *) echo "unknown flag: $arg" >&2; exit 64 ;;
    esac
done

VERSION="$(grep -E '^version\s*=\s*' "$REPO_ROOT/pyproject.toml" | head -1 | cut -d'"' -f2)"
BUILD_NUMBER="$(git -C "$REPO_ROOT" rev-parse --short HEAD 2>/dev/null || echo 0)"
MIN_OS="${DAIMON_MIN_OS:-11.0}"
DMG_BASENAME="Daimon-$VERSION"

echo "==> Building $APP_NAME $VERSION (build $BUILD_NUMBER), bundle $BUNDLE_ID"

# 0. Python 3.12+ check.
python3 - <<'PY' || { echo "Need Python 3.12+." >&2; exit 2; }
import sys
raise SystemExit(0 if sys.version_info >= (3, 12) else 1)
PY

# 1. Build venv with the app + PyInstaller.
if [[ ! -d "$VENV_DIR" ]]; then
    python3 -m venv "$VENV_DIR"
fi
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip wheel
pip install -e "$REPO_ROOT[build]"

# 2. Icons → .icns (placeholder art; replace make_icon.py output with final art).
python "$BUILD_DIR/make_icon.py" --out "$ICONS_DIR"
ICONSET_DIR="$ICONS_DIR/Daimon.iconset"
rm -rf "$ICONSET_DIR"; mkdir -p "$ICONSET_DIR"
for size in 16 32 64 128 256 512; do
    cp "$ICONS_DIR/app-${size}.png" "$ICONSET_DIR/icon_${size}x${size}.png"
    dbl=$((size * 2))
    if [[ -f "$ICONS_DIR/app-${dbl}.png" ]]; then
        cp "$ICONS_DIR/app-${dbl}.png" "$ICONSET_DIR/icon_${size}x${size}@2x.png"
    fi
done
iconutil -c icns -o "$ICONS_DIR/Daimon.icns" "$ICONSET_DIR"

# 3. PyInstaller → Daimon.app.
(
    cd "$REPO_ROOT"
    DAIMON_VERSION="$VERSION" \
    DAIMON_BUILD_NUMBER="$BUILD_NUMBER" \
    DAIMON_MIN_OS="$MIN_OS" \
    DAIMON_BUNDLE_ID="$BUNDLE_ID" \
        pyinstaller --noconfirm --clean "$BUILD_DIR/daimon.spec"
)
[[ -d "$APP_BUNDLE" ]] || { echo "PyInstaller did not produce $APP_BUNDLE" >&2; exit 1; }

# 4. Sign + harden runtime (inner Mach-O first, then frameworks, then the .app).
if [[ $DO_SIGN -eq 1 ]]; then
    echo "==> Signing with $DEV_ID"
    while IFS= read -r -d '' payload; do
        if file "$payload" | grep -q "Mach-O"; then
            codesign --force --options runtime --timestamp --sign "$DEV_ID" "$payload"
        fi
    done < <(find "$APP_BUNDLE/Contents" -type f -print0)

    if [[ -d "$APP_BUNDLE/Contents/Frameworks/Python.framework" ]]; then
        codesign --force --options runtime --timestamp --sign "$DEV_ID" \
            "$APP_BUNDLE/Contents/Frameworks/Python.framework"
    fi

    codesign --force --options runtime --timestamp --sign "$DEV_ID" \
        --identifier "$BUNDLE_ID" "$APP_BUNDLE"
    codesign --verify --strict --verbose=2 "$APP_BUNDLE"
fi

# 5. DMG via hdiutil.
DMG_PATH="$DIST_DIR/${DMG_BASENAME}.dmg"
rm -f "$DMG_PATH"; rm -rf "$DMG_ROOT"; mkdir -p "$DMG_ROOT"
ditto --noextattr --noqtn "$APP_BUNDLE" "$DMG_ROOT/$APP_NAME.app"
xattr -cr "$DMG_ROOT/$APP_NAME.app" 2>/dev/null || true
ln -s /Applications "$DMG_ROOT/Applications"
cp "$ICONS_DIR/Daimon.icns" "$DMG_ROOT/.VolumeIcon.icns"
command -v SetFile >/dev/null 2>&1 && SetFile -a C "$DMG_ROOT" || true
hdiutil create -volname "$APP_NAME $VERSION" -srcfolder "$DMG_ROOT" \
    -ov -format UDZO "$DMG_PATH"

if [[ $DO_SIGN -eq 1 ]]; then
    codesign --force --sign "$DEV_ID" --timestamp "$DMG_PATH"
fi

# 6. Notarize + staple.
if [[ $DO_NOTARIZE -eq 1 && $DO_SIGN -eq 1 ]]; then
    echo "==> Submitting for notarization (a few minutes)..."
    xcrun notarytool submit "$DMG_PATH" --keychain-profile AC_PASSWORD --wait
    xcrun stapler staple "$DMG_PATH"
fi

if [[ "${KEEP_MACOS_BUILD_PRODUCTS:-0}" != "1" ]]; then
    rm -rf "$DMG_ROOT" "$APP_BUNDLE" "$DIST_DIR/Daimon"
fi

echo "==> Build complete."
echo "    Artifact: $DMG_PATH"
echo "    Verify:   codesign --verify --deep --strict --verbose=2 \"$DMG_PATH\" && spctl --assess --type install -v \"$DMG_PATH\" && stapler validate \"$DMG_PATH\""
echo "    Publish:  gh release upload daimon-v$VERSION \"$DMG_PATH\" --clobber"
