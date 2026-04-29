# Omni Replay

Windows **instant replay**: a rolling screen buffer runs in the background. When something worth keeping happens, hit your **save hotkey** and the last *N* minutes are written to an MP4.

**[Download the installer (Releases)](https://github.com/Dust-exe/omni-replay/releases)** — grab `OmniReplay-Setup.exe`, run it, and you are done (no Python or extra downloads required for end users).

---

## Highlights

- **DXGI capture** through ffmpeg (`ddagrab`), optional **mic + system audio** (WASAPI / DirectShow fallbacks).
- **NVENC when available**, otherwise **CPU H.264** — encoder choice in Settings.
- **Global hotkeys** for save, pause/resume capture, and panel toggle (re-register after settings change).
- **Tray + side panel** (CustomTkinter), optional **REC** overlay, optional **hardware** strip (CPU/RAM/GPU/FPS).

---

## Install (end users)

1. Open **[Releases](https://github.com/Dust-exe/omni-replay/releases)**.
2. Download **`OmniReplay-Setup.exe`**.
3. Run the installer and start **Omni Replay** from the Start menu or desktop shortcut.

First launch may download **ffmpeg** into `%APPDATA%\OmniReplay\` (one-time, on-demand).

---

## Run from source (developers)

Requirements: **Windows 10/11 x64**, **Python 3.12+**.

```powershell
cd dustreplay
py -3.12 -m pip install -r ..\requirements.txt
py -3.12 main.py
```

Settings and logs: `%APPDATA%\OmniReplay\` (`settings.json`, `app.log`, `ffmpeg_stderr.log` on errors).

---

## Build portable exe + optional installer

From the repo root:

```powershell
.\build.ps1
```

Produces `dist\OmniReplay.exe` (PyInstaller one-file) and copies it to your Desktop when possible.

To also build **`dist\OmniReplay-Setup.exe`**, install [Inno Setup 6](https://jrsoftware.org/isdl.php); `build.ps1` detects `ISCC.exe` and compiles [`installer/OmniReplay.iss`](installer/OmniReplay.iss). Details: [`installer/README.md`](installer/README.md).

### Releases on GitHub (no local PC required for users)

Official binaries are produced by **GitHub Actions** when a maintainer pushes a **`v*`** version tag. See [`.github/workflows/release.yml`](.github/workflows/release.yml).

1. Align versions in [`dustreplay/version.py`](dustreplay/version.py), [`pyproject.toml`](pyproject.toml), and `#define MyAppVersion` in [`installer/OmniReplay.iss`](installer/OmniReplay.iss).
2. Commit, then: `git tag v3.2.1` and `git push origin v3.2.1`.

The workflow uploads **`OmniReplay-Setup.exe`**, **`OmniReplay.exe`**, `LICENSE`, and `LEGAL.md` to the GitHub Release for that tag.

---

## Repository layout

| Path | Role |
|------|------|
| [`dustreplay/`](dustreplay/) | Application source (`main.py`, recorder, UI, ffmpeg integration) |
| [`requirements.txt`](requirements.txt) | Runtime + PyInstaller |
| [`build.ps1`](build.ps1) | Windows build (PyInstaller + optional Inno installer) |
| [`installer/`](installer/) | Inno Setup script for `OmniReplay-Setup.exe` |

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

Use Omni Replay only where you are allowed to record screen and audio. Not affiliated with Microsoft, NVIDIA, or ffmpeg upstream.
