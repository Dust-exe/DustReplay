# Build DustReplay.exe from the dustreplay/ source tree (PyInstaller one-file).
# Default behavior: tries to pull latest code from git before building.
# Use -NoUpdate to skip git pull.
# Run in PowerShell:  cd ...\dasasd ; .\build.ps1

param(
    [switch]$NoUpdate
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

$script:isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $script:isAdmin) {
    Write-Host "  (Not Administrator: build usually works. If errors appear, try Run as administrator.)" -ForegroundColor DarkYellow
    Write-Host ""
}

function Invoke-GitUpdateIfPossible {
    param([string]$RepoRoot)

    if ($NoUpdate) { return }

    $git = Get-Command git -ErrorAction SilentlyContinue
    if (-not $git) {
        Write-Host "  (git not found - skipping auto-update)" -ForegroundColor DarkYellow
        Write-Host ""
        return
    }

    Push-Location $RepoRoot
    try {
        $inside = (& git rev-parse --is-inside-work-tree 2>$null)
        if ($LASTEXITCODE -ne 0 -or $inside -ne 'true') { return }

        $dirty = (& git status --porcelain)
        if ($dirty) {
            Write-Warning "Repo has local changes - skipping git pull. (Commit/stash first if you want updates.)"
            Write-Host ""
            return
        }

        $branch = (& git rev-parse --abbrev-ref HEAD)
        if ($LASTEXITCODE -ne 0 -or -not $branch) { return }

        Write-Host "  Updating source (git pull --ff-only)..." -ForegroundColor Cyan
        & git pull --ff-only
        Write-Host ""
    }
    catch {
        Write-Warning "Auto-update failed; building with current local code."
        Write-Host ""
    }
    finally {
        Pop-Location
    }
}

Invoke-GitUpdateIfPossible -RepoRoot $root

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

    Write-Host "  [4/5] Stopping running DustReplay..." -ForegroundColor Cyan
    try {
        $running = Get-Process -Name 'DustReplay' -ErrorAction SilentlyContinue
        if ($running) {
            $running | Stop-Process -Force -ErrorAction Stop
            # Give Windows a moment to release the EXE lock before Desktop copy.
            Start-Sleep -Seconds 1
            Write-Host "  Closed running DustReplay.exe" -ForegroundColor DarkGray
        } else {
            Write-Host "  DustReplay is not running." -ForegroundColor DarkGray
        }
    }
    catch {
        Write-Warning "Could not fully stop running DustReplay.exe. Build output is still ready."
    }

    Write-Host "  [5/5] Copy to Desktop..." -ForegroundColor Cyan
    $desk = [Environment]::GetFolderPath('Desktop')
    $deskExe = Join-Path $desk 'DustReplay.exe'
    $copied = $false
    for ($i = 1; $i -le 5; $i++) {
        try {
            Copy-Item $exe $deskExe -Force -ErrorAction Stop
            $copied = $true
            break
        }
        catch {
            if ($i -ge 5) {
                Write-Host ""
                Write-Warning "Could not copy to Desktop after 5 tries. Close every DustReplay.exe (Task Manager), then copy manually from: $exe"
                Write-Warning "Desktop path used: $deskExe"
                break
            }
            Start-Sleep -Milliseconds 600
        }
    }

    Write-Host ""
    Write-Host "  Done: $exe" -ForegroundColor Green
    if ($copied) { Write-Host "  Also copied to Desktop." -ForegroundColor Green }

    $launchExe = if ($copied -and (Test-Path $deskExe)) { $deskExe } else { $exe }
    try {
        Start-Process -FilePath $launchExe | Out-Null
        Write-Host "  Started updated app: $launchExe" -ForegroundColor Green
    }
    catch {
        Write-Warning "Could not auto-start updated app. Start it manually from dist or Desktop."
    }
}
finally {
    Pop-Location
}
