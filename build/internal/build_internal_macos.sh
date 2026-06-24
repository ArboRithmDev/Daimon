#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Build the INTERNAL macOS Daimon — the build that INCLUDES the Pacte
# cooperative channel (src/daimon/pacte/). Pacte is NOT part of the public AGPL
# distribution: it lives only on the `internal` branch, never on `main`.
#
# How Pacte gets in without touching any public file: build/daimon.spec calls
# collect_submodules("daimon"), which sweeps the package *on disk*. Built from
# the `internal` branch the pacte/ source is present, so PyInstaller bundles it
# automatically. The public spec never names Pacte, and nothing on `main` does.
#
# This wrapper only adds: a guard that Pacte source is actually present, a
# distinct bundle id so the internal app installs side-by-side with a public
# Daimon, a `-internal` artifact name, and removal of the public release
# manifest the wrapped build emits (internal builds are never published).
#
# Usage (from the repo root, on the `internal` branch):
#   ./build/internal/build_internal_macos.sh [--no-notarize] [--no-sign]
# Flags pass straight through to build/macos/build_macos.sh.
# -----------------------------------------------------------------------------
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

# 1. Hard guard: Pacte source must be present. This is the real guarantee that
#    the artifact actually contains the internal channel (works in worktrees /
#    detached HEAD too). A soft warning if we are not on the `internal` branch.
if [[ ! -f "$REPO_ROOT/src/daimon/pacte/organ.py" ]]; then
    echo "refuse: Pacte source absent (src/daimon/pacte/). Build from the 'internal' branch." >&2
    exit 3
fi
branch="$(git -C "$REPO_ROOT" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
if [[ "$branch" != "internal" ]]; then
    echo "warning: building from '$branch', not 'internal' — proceeding because Pacte source is present." >&2
fi

VERSION="$(grep -E '^version\s*=\s*' "$REPO_ROOT/pyproject.toml" | head -1 | cut -d'"' -f2)"
DIST="$REPO_ROOT/dist"

# 2. Run the standard, publicly-maintained macOS build, but with an internal
#    bundle id so the result coexists with an installed public Daimon. Keep the
#    .app/DMG products (we rename below) — override the wrapped script's cleanup.
echo "==> Internal build: Daimon $VERSION + Pacte (bundle fr.arborithm.daimon.internal)"
DAIMON_BUNDLE_ID="${DAIMON_BUNDLE_ID:-fr.arborithm.daimon.internal}" \
    "$REPO_ROOT/build/macos/build_macos.sh" "$@"

# 3. Re-tag the artifact as INTERNAL and strip the public release manifest, so
#    the internal DMG can never be mistaken for — or uploaded as — a public
#    release.
SRC_DMG="$DIST/Daimon-$VERSION.dmg"
DST_DMG="$DIST/Daimon-$VERSION-internal.dmg"
if [[ -f "$SRC_DMG" ]]; then
    mv -f "$SRC_DMG" "$DST_DMG"
fi
rm -f "$DIST/latest.json" "$DIST/SHA256SUMS"

echo "==> Internal build complete."
echo "    Artifact: $DST_DMG"
echo "    Contains the Pacte cooperative channel. DO NOT upload to the public GitHub release."
