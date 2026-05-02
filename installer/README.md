# Windows installer (`DustReplay-Setup.exe`)

Official **`DustReplay-Setup.exe`** for each release is built on **GitHub Actions** when a `v*` tag is pushed (see [`.github/workflows/release.yml`](../.github/workflows/release.yml)).

Locally, [`../build.ps1`](../build.ps1) builds `dist\DustReplay.exe` with PyInstaller, then (if available) runs **Inno Setup 6** to produce:

- `dist\DustReplay-Setup.exe`

## Prerequisite

Install [Inno Setup 6](https://jrsoftware.org/isdl.php) (default path). `ISCC.exe` is picked up automatically from:

- `C:\Program Files (x86)\Inno Setup 6\`
- `C:\Program Files\Inno Setup 6\`

If Inno Setup is missing, the app exe still builds; only the installer step is skipped.

## Version string

Bump `#define MyAppVersion` in [`DustReplay.iss`](DustReplay.iss) together with [`dustreplay/version.py`](../dustreplay/version.py) and [`pyproject.toml`](../pyproject.toml) before a release.
