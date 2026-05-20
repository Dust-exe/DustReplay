# Build DustReplay C# (WPF) — requires .NET 8 SDK
$ErrorActionPreference = "Stop"
Push-Location $PSScriptRoot
dotnet publish src/DustReplay.App/DustReplay.App.csproj -c Release -r win-x64 --self-contained false -o dist-csharp
Write-Host "Output: $PSScriptRoot\dist-csharp\DustReplay.exe"
Pop-Location
