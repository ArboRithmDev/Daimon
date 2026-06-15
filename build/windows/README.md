# Building Daimon for Windows

Mirror of `build/macos/`. Produces a signed installer that any Windows 10 2004+
(x64) user can run. The build + signing run on **your** machine with your
Authenticode certificate (Daimon's CI does not hold signing keys).

## Prerequisites

- The Windows dev venv with deps installed:
  ```powershell
  py -3.13 -m venv .venv-win
  .venv-win\Scripts\python.exe -m pip install -e ".[win,dev,build]"
  ```
  (`[win]` pulls pywin32 / windows-capture / comtypes / uiautomation / PySide6;
  `[build]` pulls PyInstaller.)
- **signtool** (Windows SDK) on PATH, and a code-signing certificate in your
  store. An **EV** cert gives instant SmartScreen reputation; an **OV** cert
  earns it over time (early downloads may see a SmartScreen warning).
- **Inno Setup 6** (`iscc` on PATH) for the installer.

## Build

```powershell
# Full: PyInstaller -> sign exes -> Inno installer -> sign installer
$env:DAIMON_CERT_SUBJECT = "Arborithm"   # your cert's subject (signtool /n)
.\build\windows\build_windows.ps1

# Fast local build (no signing, no installer)
.\build\windows\build_windows.ps1 -NoSign -NoInstaller
```

Outputs in `dist\`:
- `dist\Daimon\` — the one-dir bundle (`Daimon.exe` windowed tray/GUI,
  `daimon.exe` console dispatcher).
- `dist\Daimon-<version>-setup.exe` — the installer.

## What ships

- **`Daimon.exe`** (windowed) — double-click / Start-menu / optional sign-in
  startup. Runs the resident system-tray app; first run opens onboarding.
- **`daimon.exe`** (console) — what MCP clients invoke as `daimon serve` (stdio
  MCP server); subcommands run the setup CLI. Registration points clients at
  `…\Daimon\daimon.exe serve` (see `setup/invocation.py`).

## Version

`pyproject.toml [project].version` is the single source of truth. The tray reads
`daimon.__version__` from package metadata; the **frozen exe has no dist
metadata**, so it falls back to `_FALLBACK_VERSION`, which `tests/test_version.py`
pins to pyproject — the two cannot drift. Bump `version` in pyproject and the
`_FALLBACK_VERSION` literal together (the test enforces it).

## Notes

- **No notarization** on Windows; reputation comes from Authenticode + download
  volume (SmartScreen). Sign every public artifact.
- **Min OS = Windows 10 2004 (19041)** — required by the overlay's
  `SetWindowDisplayAffinity(WDA_EXCLUDEFROMCAPTURE)` capture-exclusion.
- Per-user install needs no elevation, matching Daimon's no-TCC model (the OS
  imposes no perception/action gate; the hands ceiling is the guardrail).
- `windows-capture` pulls `numpy` + `opencv-python`, which inflate the bundle.
  A lighter WGC binding is a future packaging optimisation.
