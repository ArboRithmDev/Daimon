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
    [switch]$NoInstaller
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path "$PSScriptRoot\..\..").Path
Set-Location $root

# Version from pyproject (single source of truth; matches __version__ fallback).
$version = (Select-String -Path "pyproject.toml" -Pattern '^version\s*=\s*"(.+)"').Matches[0].Groups[1].Value
Write-Host "Building Daimon $version" -ForegroundColor Cyan

# 1. PyInstaller ------------------------------------------------------------
& $Python -m PyInstaller "build\windows\daimon_win.spec" --clean --noconfirm
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

$distDir = Join-Path $root "dist\Daimon"
$exes = @("$distDir\Daimon.exe", "$distDir\daimon.exe")

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
if (-not $NoInstaller) {
    $iss = Join-Path $root "build\windows\daimon.iss"
    & iscc "/DMyAppVersion=$version" $iss
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup (iscc) failed" }
    $installer = Join-Path $root "dist\Daimon-$version-setup.exe"
    if ((-not $NoSign) -and (Test-Path $installer)) { Invoke-Sign $installer }
    Write-Host "Installer: $installer" -ForegroundColor Green
} else {
    Write-Host "Skipping installer (-NoInstaller)." -ForegroundColor Yellow
}

Write-Host "Done. Artifacts in dist\." -ForegroundColor Cyan
