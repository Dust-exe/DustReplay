# DustReplay

Windows **instant replay**: a rolling screen buffer runs in the background. When something worth keeping happens, hit your **save hotkey** and the last *N* minutes are written to an MP4.

**[Download (Releases)](https://github.com/Dust-exe/dustreplay/releases)** — use **`DustReplay-Setup.exe` only** (one installer: app + bundled ffmpeg + LICENSE/LEGAL into Program Files). GitHub may still list auto-generated **Source code** zip/tar.gz on the release page; that is normal and cannot be removed via our workflow.

---

## Highlights

- **DXGI capture** through ffmpeg (`ddagrab`), optional **mic + system audio** (WASAPI / DirectShow fallbacks).
- **NVENC when available**, otherwise **CPU H.264** — encoder choice in Settings.
- **Global hotkeys** for save, pause/resume capture, and panel toggle (re-register after settings change).
- **Tray + side panel** (CustomTkinter), optional **REC** overlay, optional **hardware** strip (CPU/RAM/GPU/FPS).

---

## Install (end users)

1. Open **[Releases](https://github.com/Dust-exe/dustreplay/releases)**.
2. Download **`DustReplay-Setup.exe`**.
3. Run the installer and start **DustReplay** from the Start menu or desktop shortcut.

Developers who run **`dist\DustReplay.exe`** without the installer may get a one-time **ffmpeg** download into `%APPDATA%\DustReplay\`. End users should use **`DustReplay-Setup.exe`** only.

---

## Run from source (developers)

Requirements: **Windows 10/11 x64**, **Python 3.12+**.

```powershell
cd dustreplay
py -3.12 -m pip install -r ..\requirements.txt
py -3.12 main.py
```

Settings and logs: `%APPDATA%\DustReplay\` (`settings.json`, `app.log`, `ffmpeg_stderr.log` on errors).

---

## Build portable exe + optional installer

From the repo root:

```powershell
.\build.ps1
```

Produces `dist\DustReplay.exe` (PyInstaller one-file) and copies it to your Desktop when possible.

To also build **`dist\DustReplay-Setup.exe`**, install [Inno Setup 6](https://jrsoftware.org/isdl.php); `build.ps1` detects `ISCC.exe` and compiles [`installer/DustReplay.iss`](installer/DustReplay.iss). Details: [`installer/README.md`](installer/README.md).

### Releases on GitHub (no local PC required for users)

Official binaries are produced by **GitHub Actions** when a maintainer pushes a **`v*`** version tag. See [`.github/workflows/release.yml`](.github/workflows/release.yml).

If the **Releases** page stays empty: open **Settings → Actions → General** and ensure **Actions are allowed** for this repository (forks default to disabled until you enable them).

1. Align versions in [`dustreplay/version.py`](dustreplay/version.py), [`pyproject.toml`](pyproject.toml), and `#define MyAppVersion` in [`installer/DustReplay.iss`](installer/DustReplay.iss).
2. Commit, then: `git tag v3.2.2` and `git push origin v3.2.2` (example).

The release workflow uploads **`DustReplay-Setup.exe`** only (no separate portable exe or loose license files on the release).

---

## Repository layout

| Path | Role |
|------|------|
| [`dustreplay/`](dustreplay/) | Application source (`main.py`, recorder, UI, ffmpeg integration) |
| [`requirements.txt`](requirements.txt) | Runtime + PyInstaller |
| [`build.ps1`](build.ps1) | Windows build (PyInstaller + optional Inno installer) |
| [`installer/`](installer/) | Inno Setup script for `DustReplay-Setup.exe` |

---

## Tech stack (CV-friendly one-liner)

Python 3.12 · CustomTkinter · ffmpeg (ddagrab / NVENC / libx264) · PyInstaller · global hotkeys (`keyboard`) · system tray (`pystray`).

---

## Troubleshooting

1. **Black or failed capture** — check `%APPDATA%\DustReplay\ffmpeg_stderr.log` after a failure.
2. **Hotkeys not firing** — run as Administrator; see `app.log` for registration errors.
3. **NVENC errors on non-NVIDIA machines** — set encoder to **CPU H.264** in Settings or leave **Auto**.

---

## License and legal

- **License:** [MIT](LICENSE)
- **Disclaimer (plain language):** [LEGAL.md](LEGAL.md)

Recording laws and third-party terms are **your** responsibility. The software is provided **as is** without warranty.

---

## Disclaimer (short)

Use DustReplay only where you are allowed to record screen and audio. Not affiliated with Microsoft, NVIDIA, or ffmpeg upstream.
