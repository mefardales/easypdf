<#
.SYNOPSIS
    Builds EasyPDF into an .exe and produces the Windows installer.

.DESCRIPTION
    1. Creates a virtual environment in .venv (if it is not there yet)
    2. Installs the dependencies and PyInstaller
    3. Regenerates the icon
    4. Packages with PyInstaller  -> dist\EasyPDF\EasyPDF.exe
    5. Builds the installer with Inno Setup -> dist\installer\EasyPDF-<version>-Setup.exe

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1

.NOTES
    Inno Setup 6 is optional: without it only the dist\EasyPDF folder is
    produced (which is already distributable zipped up).
    Download: https://jrsoftware.org/isdl.php
#>
[CmdletBinding()]
param(
    [switch]$SkipInstaller,
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
Write-Host "== EasyPDF: building in $root" -ForegroundColor Cyan

# 1. Virtual environment ---------------------------------------------------
$venv = Join-Path $root ".venv"
if (-not (Test-Path $venv)) {
    Write-Host "-- Creating the virtual environment" -ForegroundColor Yellow
    & $Python -m venv $venv
}
$py = Join-Path $venv "Scripts\python.exe"

# 2. Dependencies ----------------------------------------------------------
Write-Host "-- Installing dependencies" -ForegroundColor Yellow
& $py -m pip install --upgrade pip --quiet
& $py -m pip install -r (Join-Path $root "requirements-dev.txt") --quiet

# 3. Icon ------------------------------------------------------------------
Write-Host "-- Building the icon" -ForegroundColor Yellow
& $py (Join-Path $root "tools\make_icon.py")

# 4. Tests (quick, so nothing broken gets packaged) ------------------------
Write-Host "-- Running the tests" -ForegroundColor Yellow
& $py -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "The tests failed; nothing will be packaged." }

# 5. PyInstaller -----------------------------------------------------------
Write-Host "-- Packaging with PyInstaller" -ForegroundColor Yellow
Remove-Item -Recurse -Force (Join-Path $root ".pyinstaller") -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force (Join-Path $root "dist\EasyPDF") -ErrorAction SilentlyContinue
& $py -m PyInstaller (Join-Path $root "packaging\easypdf.spec") --noconfirm --clean --workpath (Join-Path $root ".pyinstaller")
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed." }

$exe = Join-Path $root "dist\EasyPDF\EasyPDF.exe"
if (-not (Test-Path $exe)) { throw "$exe was not built" }
Write-Host "   OK -> $exe" -ForegroundColor Green

# 6. Installer -------------------------------------------------------------
if ($SkipInstaller) {
    Write-Host "== Done (no installer)" -ForegroundColor Cyan
    exit 0
}

$iscc = @(
    "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
    "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
    "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $iscc) {
    $iscc = (Get-Command ISCC.exe -ErrorAction SilentlyContinue).Source
}

if (-not $iscc) {
    Write-Warning "Inno Setup 6 not found: the installer is skipped."
    Write-Warning "Install it from https://jrsoftware.org/isdl.php and run this again."
    exit 0
}

Write-Host "-- Building the installer with $iscc" -ForegroundColor Yellow
& $iscc (Join-Path $root "packaging\installer.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup failed." }

# 7. Copy into build\ -----------------------------------------------------
$buildDir = Join-Path $root "build"
New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
$version = (Select-String -Path (Join-Path $root "src\easypdf\__init__.py") -Pattern '__version__ = "(.+)"').Matches[0].Groups[1].Value

Get-ChildItem (Join-Path $root "dist\installer") -Filter *.exe |
    ForEach-Object {
        Copy-Item $_.FullName (Join-Path $buildDir $_.Name) -Force
        Write-Host "   OK -> $(Join-Path $buildDir $_.Name)" -ForegroundColor Green
    }

$zip = Join-Path $buildDir "EasyPDF-$version-windows-x64-portable.zip"
Remove-Item $zip -ErrorAction SilentlyContinue
Compress-Archive -Path (Join-Path $root "dist\EasyPDF\*") -DestinationPath $zip
Write-Host "   OK -> $zip" -ForegroundColor Green
Write-Host "== Done" -ForegroundColor Cyan
