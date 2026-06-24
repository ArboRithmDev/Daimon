# Internal build — Daimon + Pacte

The **Pacte cooperative channel** (`src/daimon/pacte/`) is an internal-only
feature: it lets an autonomous agent drive and observe in-app manipulation
(e.g. a Qt `QGraphicsScene`) through a cooperating app's `--dev` endpoint. It is
**not** part of the public AGPL distribution.

## Branch model

- **`main`** — public. Pushed to `origin` (github.com/ArboRithmDev/Daimon),
  source of public releases. **Never contains Pacte.**
- **`internal`** — private, local-only (not pushed to the public remote). It is
  `main` + the Pacte commits. Internal builds come from here.

Keep `internal` current with public work by merging forward:

```bash
git checkout internal
git merge main        # pull public changes into internal; never the reverse
```

Never merge `internal` into `main`, and never push `internal` to the public
`origin`. A future `git push origin main` is safe — `main` has no Pacte.

## Why no public file mentions Pacte

`build/daimon.spec` (and `build/windows/daimon_win.spec`) bundle the app with
`collect_submodules("daimon")`, which sweeps the package **on disk**. Built from
`internal`, the `pacte/` source is present and PyInstaller includes it
automatically. Built from `main`, it simply isn't there. So the public spec —
and everything on `main` — never references Pacte.

## Building

macOS (on this Mac, from the `internal` branch):

```bash
./build/internal/build_internal_macos.sh            # signed + notarized
./build/internal/build_internal_macos.sh --no-notarize --no-sign   # fast local
```

Windows (on the Windows box, from the `internal` branch):

```powershell
.\build\internal\build_internal_windows.ps1 -NoSign -NoInstaller   # fast local
.\build\internal\build_internal_windows.ps1                        # signed + installer
```

Each wrapper: (1) refuses unless the Pacte source is present; (2) runs the
standard public build script (so build logic stays DRY and maintained in one
place); (3) re-tags the artifact `…-internal…`; (4) deletes the
`latest.json` / `SHA256SUMS` release manifest the wrapped build emits — internal
builds are never published. macOS also uses the bundle id
`fr.arborithm.daimon.internal` so the internal app installs side-by-side with a
public Daimon.

Artifacts:
- macOS: `dist/Daimon-<version>-internal.dmg`
- Windows: `dist/Daimon-<version>-internal-setup.exe`

**Do not upload internal artifacts to the public GitHub release.**
