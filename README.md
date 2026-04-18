<<<<<<< HEAD
# DustReplay

**DustReplay** is a Windows desktop app that keeps a **rolling screen buffer** (like an instant replay). When something worth keeping happens, press a **global hotkey** to write the last *N* minutes to an MP4 in your output folder.

- **Capture**: DXGI Desktop Duplication via ffmpeg (`ddagrab`), optional microphone + system audio (WASAPI loopback or DirectShow fallbacks).
- **Encode**: **Auto-detect NVIDIA NVENC**; falls back to **CPU H.264 (libx264)** when NVENC is unavailable (AMD/Intel or headless GPUs).
- **UI**: Side panel (CustomTkinter) + system tray; optional small **REC** overlay.
- **Hotkeys**: Save clip, stop/start capture, toggle panel — all **re-register** when you change them in Settings.

## Requirements

- **Windows 10/11** (64-bit)
- **Python 3.12+** (for running from source)
- **ffmpeg** is downloaded automatically on first launch (~80 MB, [BtbN Windows build](https://github.com/BtbN/FFmpeg-Builds))
- **Administrator** rights are often required for global hotkeys (`keyboard` library) — if hotkeys fail, try *Run as administrator*.

## Quick start (from source)

```powershell
cd dustreplay
py -3.12 -m pip install -r ..\requirements.txt
py -3.12 main.py
```

Settings and logs live under `%APPDATA%\DustReplay\` (including `settings.json` and `app.log`).

## Build a single `DustReplay.exe`

From the repository root:

```powershell
.\build.ps1
```

The script installs dependencies, runs PyInstaller, and copies `DustReplay.exe` to your **Desktop** (same behaviour as the legacy `instant_replay` scripts).

## Project layout

| Path | Role |
|------|------|
| `dustreplay/` | Application source (`main.py`, UI, recorder, ffmpeg integration) |
| `requirements.txt` | Runtime + PyInstaller |
| `build.ps1` | Windows one-file executable build |
| `instant_replay/` | Legacy admin wrappers (optional); prefer `build.ps1` |

## Configuration highlights

| Key | Meaning |
|-----|---------|
| `buffer_minutes` | How far back segments are kept on disk |
| `save_minutes` | How much of that buffer is merged when you save |
| `monitor_index` | **1-based** display index (matches the Settings list) |
| `video_encoder` | `auto` / `nvenc` / `cpu` |
| `hotkey_save`, `hotkey_toggle`, `panel_hotkey` | Passed to the `keyboard` library |

## Open source & your CV

- **License**: [MIT](LICENSE) — free to use in portfolios and commercial projects with attribution.
- **Suggested GitHub description**: *Windows instant replay app — rolling DXGI capture, ffmpeg NVENC/x264, global hotkeys (Python + CustomTkinter).*
- Replace `Homepage` in `pyproject.toml` with your real repository URL before publishing.

## Troubleshooting

1. **Black / failed capture** — open `%APPDATA%\DustReplay\ffmpeg_stderr.log` after a failure.
2. **Hotkeys dead** — run as Administrator; check `app.log` for registration errors.
3. **NVENC errors on non-NVIDIA PCs** — set **Video encoder** to **CPU H.264** in Settings (or leave **Auto**).

## Disclaimer

This tool records the screen and audio. Only use it where you have permission to record. Not affiliated with NVIDIA, Microsoft, or ffmpeg upstream projects.
=======
# dustreplay
>>>>>>> c9c9d5b2f334be9ed4b335e9946baf422212d2c2
