# Build DustReplay.exe from the dustreplay/ source tree (PyInstaller one-file).
# Does NOT run git pull - run: git pull first for latest code.
# Run in PowerShell:  cd ...\dasasd ; .\build.ps1

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

$script:isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $script:isAdmin) {
    Write-Host "  (Not Administrator: build usually works. If errors appear, try Run as administrator.)" -ForegroundColor DarkYellow
    Write-Host ""
}
$pkg = Join-Path $root 'dustreplay'
$distDir = Join-Path $root 'dist'
$workDir = Join-Path $root 'build\pyinstaller_work'
$specDir = Join-Path $root 'build'

Write-Host ""
Write-Host "  DustReplay build - PyInstaller" -ForegroundColor Magenta
Write-Host "  Source: $pkg" -ForegroundColor DarkGray
Write-Host ""

if (-not (Test-Path $pkg)) { throw "Missing folder: $pkg" }

Push-Location $pkg
try {
    Write-Host "  [1/4] pip install..." -ForegroundColor Cyan
    & py -3.12 -m pip install -r (Join-Path $root 'requirements.txt') --upgrade

    Write-Host "  [2/4] icon.ico..." -ForegroundColor Cyan
    if (Test-Path '_mkicon.py') { & py -3.12 _mkicon.py }

    New-Item -ItemType Directory -Force -Path $distDir | Out-Null
    New-Item -ItemType Directory -Force -Path $workDir | Out-Null
    New-Item -ItemType Directory -Force -Path $specDir | Out-Null

    $pyiArgs = @(
        '-m', 'PyInstaller',
        '--onefile', '--noconsole',
        '--name', 'DustReplay',
        '--distpath', $distDir,
        '--workpath', $workDir,
        '--specpath', $specDir,
        '--hidden-import', 'pystray._win32',
        '--hidden-import', 'PIL._tkinter_finder',
        '--hidden-import', 'monitors',
        '--hidden-import', 'audio_devices',
        '--hidden-import', 'overlay',
        '--hidden-import', 'encoding',
        '--hidden-import', 'version',
        '--hidden-import', 'stats_window'
    )
    $ico = Join-Path $pkg 'icon.ico'
    if (Test-Path $ico) { $pyiArgs += "--icon=$ico" }
    $pyiArgs += 'main.py'

    Write-Host "  [3/4] PyInstaller (may take several minutes)..." -ForegroundColor Cyan
    & py -3.12 @pyiArgs
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller exit $LASTEXITCODE" }

    $exe = Join-Path $distDir 'DustReplay.exe'
    if (-not (Test-Path $exe)) { throw "Expected output missing: $exe" }

    Write-Host "  [4/4] Copy to Desktop..." -ForegroundColor Cyan
    $desk = [Environment]::GetFolderPath('Desktop')
    $deskExe = Join-Path $desk 'DustReplay.exe'
    try {
        Copy-Item $exe $deskExe -Force -ErrorAction Stop
        $copied = $true
    }
    catch {
        $copied = $false
        Write-Host ""
        Write-Warning "Could not copy to Desktop (close DustReplay.exe if it is running, then copy manually from dist)."
    }

    Write-Host ""
    Write-Host "  Done: $exe" -ForegroundColor Green
    if ($copied) { Write-Host "  Also copied to Desktop." -ForegroundColor Green }
}
finally {
    Pop-Location
}
