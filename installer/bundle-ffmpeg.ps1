# Download win64 ffmpeg (BtbN build) into ../bundle/ffmpeg/ffmpeg.exe for Inno Setup.
# Idempotent: skips if target already exists and is non-empty.
#
# Do not use $PSScriptRoot inside param() defaults — it can be empty when the param block is bound.

param(
    [string]$RepoRoot = ""
)

$ErrorActionPreference = 'Stop'
if (-not $RepoRoot) {
    $RepoRoot = Split-Path -Parent $PSScriptRoot
}
if (-not (Test-Path -LiteralPath $RepoRoot)) {
    throw "bundle-ffmpeg: RepoRoot is not a valid path: '$RepoRoot'"
}

$outDir = Join-Path $RepoRoot 'bundle\ffmpeg'
$target = Join-Path $outDir 'ffmpeg.exe'
$url = 'https://github.com/BtbN/ffmpeg-builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip'

if ((Test-Path $target) -and ((Get-Item $target).Length -gt 1MB)) {
    Write-Host "  bundle-ffmpeg: already present: $target" -ForegroundColor DarkGray
    exit 0
}

New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$zip = Join-Path $env:TEMP ("ffbundle_" + [Guid]::NewGuid().ToString('n') + '.zip')
$expand = Join-Path $env:TEMP ("ffbundle_" + [Guid]::NewGuid().ToString('n'))

try {
    Write-Host "  bundle-ffmpeg: RepoRoot=$RepoRoot" -ForegroundColor DarkGray
    Write-Host "  bundle-ffmpeg: downloading (may take several minutes)..." -ForegroundColor Cyan
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
    Expand-Archive -LiteralPath $zip -DestinationPath $expand -Force
    $ff = Get-ChildItem -Path $expand -Recurse -Filter 'ffmpeg.exe' -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match 'win64' } |
        Select-Object -First 1
    if (-not $ff) {
        $ff = Get-ChildItem -Path $expand -Recurse -Filter 'ffmpeg.exe' -ErrorAction SilentlyContinue |
            Select-Object -First 1
    }
    if (-not $ff) { throw "ffmpeg.exe not found inside downloaded archive." }
    Copy-Item -LiteralPath $ff.FullName -Destination $target -Force
    Write-Host "  bundle-ffmpeg: OK -> $target" -ForegroundColor Green
}
finally {
    Remove-Item -LiteralPath $zip -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $expand -Recurse -Force -ErrorAction SilentlyContinue
}
