<#
.SYNOPSIS
    Build (and optionally sign + package) Daimon for Windows.

.DESCRIPTION
    Mirrors build/macos/build_macos.sh. Steps:
      1. PyInstaller -> dist/Daimon (Daimon.exe windowed + daimon.exe console).
      2. (optional) Authenticode-sign both exes with signtool.
      3. (optional) Inno Setup -> dist/Daimon-<version>-setup.exe, then sign it.

    Escape hatches: -NoSign skips signing, -NoInstaller skips Inno Setup
    (fast local build = `.\build\windows\build_windows.ps1 -NoSign -NoInstaller`).

.PARAMETER CertSubject
    Subject name of the Authenticode code-signing cert in the user/machine store
    (e.g. "Arborithm"). Used by signtool /n. Required unless -NoSign.

.NOTES
    Prereqs: the Windows venv with deps installed, PyInstaller, signtool (Windows
    SDK) for signing, and Inno Setup 6 (iscc on PATH) for the installer.
    An EV cert gives instant SmartScreen reputation; an OV cert builds reputation
    over time.
#>
[CmdletBinding()]
param(
    [string]$Python = ".venv-win\Scripts\python.exe",
    [string]$CertSubject = $env:DAIMON_CERT_SUBJECT,
    [string]$TimestampUrl = "http://timestamp.digicert.com",
    [switch]$NoSign,
    [switch]$NoInstaller,
    [switch]$Fast   # skip --clean: reuse PyInstaller's analysis cache (fast dev rebuilds)
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path "$PSScriptRoot\..\..").Path
Set-Location $root

# Version from pyproject (single source of truth; matches __version__ fallback).
$version = (Select-String -Path "pyproject.toml" -Pattern '^version\s*=\s*"(.+)"').Matches[0].Groups[1].Value
Write-Host "Building Daimon $version" -ForegroundColor Cyan

# 0. Stop any running Daimon.exe -------------------------------------------
# A running instance (MCP server spawned by a client, the tray, or the overlay)
# holds dist\Daimon files open, so PyInstaller can't overwrite them.
$running = Get-Process Daimon -ErrorAction SilentlyContinue
if ($running) {
    Write-Host "Stopping $($running.Count) running Daimon.exe..." -ForegroundColor Yellow
    $running | Stop-Process -Force
    Start-Sleep -Milliseconds 600
}

# 0.5 Brand assets ----------------------------------------------------------
# The exe/installer icon (Daimon.ico) and the face web bundle the webviews load
# are generated here (not committed) so the build is their single source of
# truth. Both are best-effort: a machine without QtSvg/Node still produces a
# working exe (iconless / faceless) rather than failing the whole build.
Write-Host "Generating brand icon (Daimon.ico)..." -ForegroundColor Cyan
& $Python build\make_icon.py --ico build\generated-icons\Daimon.ico
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: icon generation failed; exe ships without a branded icon." -ForegroundColor Yellow
}

Write-Host "Building face web bundle (npm + esbuild)..." -ForegroundColor Cyan
& $Python build\make_face.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "WARNING: face bundle build failed; face surfaces unavailable." -ForegroundColor Yellow
}

# 1. PyInstaller ------------------------------------------------------------
# --clean for release (cold) builds; -Fast skips it to reuse the cache (dev).
$piArgs = @("build\windows\daimon_win.spec", "--noconfirm")
if (-not $Fast) { $piArgs = @("--clean") + $piArgs }
& $Python -m PyInstaller @piArgs
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$distDir = Join-Path $root "dist\Daimon"
$exes = @("$distDir\Daimon.exe")

# 2. Sign the exes ----------------------------------------------------------
function Invoke-Sign($path) {
    if (-not $CertSubject) { throw "CertSubject (or `$env:DAIMON_CERT_SUBJECT) required to sign; use -NoSign to skip." }
    & signtool sign /n $CertSubject /fd SHA256 /tr $TimestampUrl /td SHA256 $path
    if ($LASTEXITCODE -ne 0) { throw "signtool failed for $path" }
}

if (-not $NoSign) {
    foreach ($e in $exes) { Invoke-Sign $e }
    Write-Host "Signed exes." -ForegroundColor Green
} else {
    Write-Host "Skipping signing (-NoSign)." -ForegroundColor Yellow
}

# 3. Installer (Inno Setup) -------------------------------------------------
function Resolve-Iscc {
    $cmd = Get-Command iscc -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $std = @(
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 5\ISCC.exe"
    )
    return ($std | Where-Object { Test-Path $_ } | Select-Object -First 1)
}

if (-not $NoInstaller) {
    $iscc = Resolve-Iscc
    if (-not $iscc) {
        throw "Inno Setup (ISCC.exe) not found on PATH or in Program Files. " +
              "Install it (winget install --id JRSoftware.InnoSetup -e) or pass -NoInstaller."
    }
    $iss = Join-Path $root "build\windows\daimon.iss"
    & $iscc "/DMyAppVersion=$version" $iss
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup (ISCC.exe) failed" }
    $installer = Join-Path $root "dist\Daimon-$version-setup.exe"
    if ((-not $NoSign) -and (Test-Path $installer)) { Invoke-Sign $installer }
    Write-Host "Installer: $installer" -ForegroundColor Green

    # Release manifest: add the win64 asset to dist\latest.json + SHA256SUMS
    # (publish both to the GitHub release; clients verify the hash before applying).
    if (Test-Path $installer) {
        & $Python "build\make_manifest.py" --version $version `
            --out (Join-Path $root "dist") --platform win64 --asset $installer
    }
} else {
    Write-Host "Skipping installer (-NoInstaller)." -ForegroundColor Yellow
}

Write-Host "Done. Artifacts in dist\." -ForegroundColor Cyan
