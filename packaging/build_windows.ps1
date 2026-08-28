<#
.SYNOPSIS
    Compila EasyPDF a .exe y genera el instalador de Windows.

.DESCRIPTION
    1. Crea (si hace falta) un entorno virtual en .venv
    2. Instala las dependencias y PyInstaller
    3. Regenera el icono
    4. Empaqueta con PyInstaller  -> dist\EasyPDF\EasyPDF.exe
    5. Compila el instalador con Inno Setup -> dist\installer\EasyPDF-<version>-Setup.exe

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File packaging\build_windows.ps1

.NOTES
    Inno Setup 6 es opcional: si no esta instalado se genera solo la carpeta
    dist\EasyPDF (que ya es distribuible comprimida en un .zip).
    Descarga: https://jrsoftware.org/isdl.php
#>
[CmdletBinding()]
param(
    [switch]$SkipInstaller,
    [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
Write-Host "== EasyPDF: compilando en $root" -ForegroundColor Cyan

# 1. Entorno virtual -------------------------------------------------------
$venv = Join-Path $root ".venv"
if (-not (Test-Path $venv)) {
    Write-Host "-- Creando entorno virtual" -ForegroundColor Yellow
    & $Python -m venv $venv
}
$py = Join-Path $venv "Scripts\python.exe"

# 2. Dependencias ----------------------------------------------------------
Write-Host "-- Instalando dependencias" -ForegroundColor Yellow
& $py -m pip install --upgrade pip --quiet
& $py -m pip install -r (Join-Path $root "requirements-dev.txt") --quiet

# 3. Icono -----------------------------------------------------------------
Write-Host "-- Generando icono" -ForegroundColor Yellow
& $py (Join-Path $root "tools\make_icon.py")

# 4. Pruebas (rapidas, para no empaquetar algo roto) -----------------------
Write-Host "-- Ejecutando pruebas" -ForegroundColor Yellow
& $py -m pytest -q
if ($LASTEXITCODE -ne 0) { throw "Las pruebas han fallado; no se empaqueta." }

# 5. PyInstaller -----------------------------------------------------------
Write-Host "-- Empaquetando con PyInstaller" -ForegroundColor Yellow
Remove-Item -Recurse -Force (Join-Path $root "build") -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force (Join-Path $root "dist\EasyPDF") -ErrorAction SilentlyContinue
& $py -m PyInstaller (Join-Path $root "packaging\easypdf.spec") --noconfirm --clean
if ($LASTEXITCODE -ne 0) { throw "PyInstaller ha fallado." }

$exe = Join-Path $root "dist\EasyPDF\EasyPDF.exe"
if (-not (Test-Path $exe)) { throw "No se genero $exe" }
Write-Host "   OK -> $exe" -ForegroundColor Green

# 6. Instalador ------------------------------------------------------------
if ($SkipInstaller) {
    Write-Host "== Listo (sin instalador)" -ForegroundColor Cyan
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
    Write-Warning "Inno Setup 6 no encontrado: se omite el instalador."
    Write-Warning "Instalalo desde https://jrsoftware.org/isdl.php y vuelve a ejecutar."
    exit 0
}

Write-Host "-- Compilando el instalador con $iscc" -ForegroundColor Yellow
& $iscc (Join-Path $root "packaging\installer.iss")
if ($LASTEXITCODE -ne 0) { throw "Inno Setup ha fallado." }

Get-ChildItem (Join-Path $root "dist\installer") -Filter *.exe |
    ForEach-Object { Write-Host "   OK -> $($_.FullName)" -ForegroundColor Green }
Write-Host "== Listo" -ForegroundColor Cyan
