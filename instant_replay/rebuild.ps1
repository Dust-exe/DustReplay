# Legacy entry — delegates to repository build.ps1 (PyInstaller from dustreplay/).
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot
$build = Join-Path $repoRoot 'build.ps1'
if (-not (Test-Path $build)) { throw "Missing: $build" }
Write-Host "Delegating to: $build" -ForegroundColor DarkGray
& $build
