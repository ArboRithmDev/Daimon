<#
.SYNOPSIS
    Build the INTERNAL Windows Daimon — the build that INCLUDES the Pacte
    cooperative channel (src\daimon\pacte\). Mirror of build_internal_macos.sh.

.DESCRIPTION
    Pacte is NOT in the public AGPL distribution: it lives only on the `internal`
    branch, never on `main`. build\windows\daimon_win.spec uses
    collect_submodules("daimon"), which sweeps the package on disk, so a build
    from the `internal` branch bundles pacte automatically — no public file ever
    names Pacte.

    This wrapper adds: a guard that Pacte source is present, a `-internal`
    artifact name, and removal of the public release manifest the wrapped build
    emits (internal builds are never published).

    Flags pass straight through to build\windows\build_windows.ps1
    (e.g. -NoSign -NoInstaller -Fast).

.NOTES
    Coexistence note: unlike macOS (distinct bundle id), this does not change the
    Inno Setup AppId, so the internal installer upgrades-in-place over a public
    Daimon rather than installing side-by-side. Add a distinct /DMyAppId to
    daimon.iss if side-by-side install is needed.
#>
[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    $PassThrough
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path "$PSScriptRoot\..\..").Path
Set-Location $root

# 1. Hard guard: Pacte source must be present (the real proof the artifact
#    contains the internal channel). Soft warning if not on the `internal` branch.
if (-not (Test-Path "$root\src\daimon\pacte\organ.py")) {
    throw "refuse: Pacte source absent (src\daimon\pacte\). Build from the 'internal' branch."
}
$branch = (git -C $root rev-parse --abbrev-ref HEAD 2>$null)
if ($branch -ne "internal") {
    Write-Host "warning: building from '$branch', not 'internal' — proceeding because Pacte source is present." -ForegroundColor Yellow
}

$version = (Select-String -Path "pyproject.toml" -Pattern '^version\s*=\s*"(.+)"').Matches[0].Groups[1].Value
$dist = Join-Path $root "dist"

# 2. Run the standard, publicly-maintained Windows build.
Write-Host "==> Internal build: Daimon $version + Pacte" -ForegroundColor Cyan
& "$root\build\windows\build_windows.ps1" @PassThrough
if ($LASTEXITCODE -ne 0) { throw "build_windows.ps1 failed" }

# 3. Re-tag the artifact as INTERNAL and strip the public release manifest.
$srcExe = Join-Path $dist "Daimon-$version-setup.exe"
$dstExe = Join-Path $dist "Daimon-$version-internal-setup.exe"
if (Test-Path $srcExe) { Move-Item -Force $srcExe $dstExe }
Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $dist "latest.json"), (Join-Path $dist "SHA256SUMS")

Write-Host "==> Internal build complete." -ForegroundColor Cyan
Write-Host "    Artifact: $dstExe"
Write-Host "    Contains the Pacte cooperative channel. DO NOT upload to the public GitHub release." -ForegroundColor Yellow
