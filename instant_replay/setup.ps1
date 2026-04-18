# First-time setup: install Python deps, then build DustReplay.exe (requires Administrator).
$ErrorActionPreference = 'Stop'
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Start-Process powershell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`"" -Verb RunAs
    exit
}

$repoRoot = Split-Path $PSScriptRoot
$req = Join-Path $repoRoot 'requirements.txt'
$pkg = Join-Path $repoRoot 'dustreplay'

Write-Host ""
Write-Host "  DustReplay — dependency install" -ForegroundColor Magenta
Write-Host ""

if (-not (Test-Path $req)) { throw "Missing: $req" }
& py -3.12 -m pip install -r $req --upgrade

Write-Host ""
Write-Host "  To run from source:" -ForegroundColor Green
Write-Host "    cd `"$pkg`"" -ForegroundColor Gray
Write-Host "    py -3.12 main.py" -ForegroundColor Gray
Write-Host ""
Write-Host "  Building Desktop\DustReplay.exe next..." -ForegroundColor Green
Write-Host ""

& (Join-Path $repoRoot 'build.ps1')
