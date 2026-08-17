"""DustReplay v4.0 — MKV Ring-Buffer Recorder Engine.

Architecture:
  - Single continuous FFmpeg process writes 30-second MKV segments.
  - MKV segments are valid mid-write (no moov atom dependency like MP4).
  - Save = collect closed segments + live-copy active segment → concat to MP4.
  - FFmpeg is NEVER stopped during save → zero gap.
  - Cleanup thread prunes segments older than buffer_minutes.
  - No game mode, no profile switching, no runtime restarts.
"""

from __future__ import annotations

import config
import encoding
import glob
import logging
import os
import psutil
import shutil
import subprocess
import threading
import time

logger = logging.getLogger(__name__)

# ── Internal constants ──────────────────────────────────────────────────────
_SEGMENT_SECONDS = 30          # MKV segment duration
_CLEANUP_INTERVAL = 10         # seconds between cleanup sweeps
_TAIL_COPY_TIMEOUT = 30        # seconds to wait for tail segment copy
_TAIL_MIN_BYTES = 8_192        # minimum size for a usable segment
_PID_FILE = os.path.join(config.APPDATA_DIR, "ffmpeg.pid")
_SEG_PATTERN = "seg_*.mkv"    # glob pattern for ring buffer segments
_SEG_STRFTIME = "seg_%Y%m%d_%H%M%S.mkv"


def get_ffmpeg_path():
    p = config.resolve_ffmpeg_exe()
    if p:
        return p
    raise FileNotFoundError(
        "ffmpeg.exe not found. Reinstall or run first-time setup again."
    )


def resolve_wasapi_exe() -> str | None:
    """Locate wasapi_loopback.exe across frozen exe, bundle, and dev paths."""
    import sys
    candidates = []
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidates.append(os.path.join(exe_dir, "wasapi_loopback.exe"))
        candidates.append(os.path.join(exe_dir, "_internal", "wasapi_loopback.exe"))
        if hasattr(sys, "_MEIPASS"):
            candidates.append(os.path.join(sys._MEIPASS, "wasapi_loopback.exe"))
    candidates.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "wasapi_loopback.exe"))
    candidates.append(os.path.join(config.APPDATA_DIR, "wasapi_loopback.exe"))
    for p in candidates:
        if p and os.path.isfile(p):
            return p
    return None


# ── Stale process cleanup ──────────────────────────────────────────────────

def _kill_stale_ffmpeg():
    try:
        if not os.path.isfile(_PID_FILE):
            return
        with open(_PID_FILE, "r") as f:
            old_pid = int(f.read().strip())
        try:
            if psutil.Process(old_pid).name().lower() == 'ffmpeg.exe':
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(old_pid)],
                    capture_output=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                logger.info("Terminated stale ffmpeg PID=%s", old_pid)
            else:
                logger.warning("Stale PID %s is not ffmpeg, ignoring", old_pid)
        except psutil.NoSuchProcess:
            pass
    except Exception as e:
        logger.debug("Stale PID cleanup: %s", e)
    try:
        os.remove(_PID_FILE)
    except Exception:
        pass


# ── DirectShow system audio fallback ────────────────────────────────────────

def _find_dshow_sys_audio(ff, exclude_mic=""):
    try:
        from audio_devices import list_dshow_audio as _lda
        devs = _lda(ff)
    except Exception:
        return None
    if not devs:
        return None
    _keywords = [
        "stereo mix", "wave out mix", "what u hear",
        "cable output", "virtual audio cable", "blackhole",
        "voicemeeter output", "voicemeeter vaio3 output",
        "voicemeeter out b1", "voicemeeter out",
    ]
    dl = [(d, d.lower()) for d in devs if d != exclude_mic]
    for kw in _keywords:
        for d, dlow in dl:
            if kw in dlow:
                logger.info("dshow system-audio candidate: '%s'", d)
                return d
    return None


# ── Monitor geometry ────────────────────────────────────────────────────────

def get_monitor_geometry(monitor_index: int = 1) -> tuple[int, int, int, int]:
    """Return (offset_x, offset_y, width, height) for specified monitor (1-based index)."""
    import ctypes

    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_ulong),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", ctypes.c_ulong),
            ("szDevice", ctypes.c_wchar * 32)
        ]

    monitors = []

    def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
        mi = MONITORINFOEXW()
        mi.cbSize = ctypes.sizeof(MONITORINFOEXW)
        if ctypes.windll.user32.GetMonitorInfoW(hMonitor, ctypes.byref(mi)):
            rc = mi.rcMonitor
            w = rc.right - rc.left
            h = rc.bottom - rc.top
            monitors.append((rc.left, rc.top, w, h))
        return True

    try:
        MON_ENUM_PROC = ctypes.WINFUNCTYPE(
            ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(RECT), ctypes.c_size_t
        )
        ctypes.windll.user32.EnumDisplayMonitors(None, None, MON_ENUM_PROC(callback), 0)
    except Exception as e:
        logger.warning("Monitor enumeration error: %s", e)

    if not monitors:
        return (0, 0, 1920, 1080)

    idx = max(0, min(monitor_index - 1, len(monitors) - 1))
    return monitors[idx]


def get_all_monitors_geometry() -> tuple[int, int, int, int]:
    """Return bounding box (offset_x, offset_y, width, height) covering ALL monitors."""
    import ctypes

    class RECT(ctypes.Structure):
        _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                    ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

    rects = []

    def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
        rc = lprcMonitor.contents
        rects.append((rc.left, rc.top, rc.right, rc.bottom))
        return True

    try:
        MON_ENUM_PROC = ctypes.WINFUNCTYPE(
            ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(RECT), ctypes.c_size_t
        )
        ctypes.windll.user32.EnumDisplayMonitors(None, None, MON_ENUM_PROC(callback), 0)
    except Exception as e:
        logger.warning("Monitor enumeration error: %s", e)

    if not rects:
        return (0, 0, 1920, 1080)

    min_x = min(r[0] for r in rects)
    min_y = min(r[1] for r in rects)
    max_x = max(r[2] for r in rects)
    max_y = max(r[3] for r in rects)
    return (min_x, min_y, max_x - min_x, max_y - min_y)


# ── Video filter helpers ────────────────────────────────────────────────────

def _capture_scale_filter(max_h_override: int | None = None) -> str:
    """Even dimensions for yuv420p; max height caps pixels (less RAM/CPU for ffmpeg)."""
    if max_h_override is not None:
        max_h = max_h_override
    else:
        try:
            max_h = int(config.get("capture_max_height") or 0)
        except (TypeError, ValueError):
            max_h = 0
    if max_h <= 0:
        return "scale=trunc(iw/2)*2:trunc(ih/2)*2"
    max_h = max(240, min(max_h, 4320))
    return f"scale=trunc(iw*min(1\\,{max_h}/ih)/2)*2:trunc(min(ih\\,{max_h})/2)*2"


def _capture_flip_suffix() -> str:
    """Extra video filters after scale for physically rotated / mirrored monitors."""
    raw = (config.get("capture_flip") or "none").lower().strip()
    if raw in ("none", "normal", "0", ""):
        return ""
    if raw in ("v", "vflip", "vertical", "flip_vertical", "invert_y", "ters", "up_down"):
        return ",vflip"
    if raw in ("h", "hflip", "horizontal", "flip_horizontal", "mirror", "invert_x", "ayna"):
        return ",hflip"
    if raw in (
        "180", "rotate180", "rotate_180", "both", "invert",
        "upside_down", "flip_both",
    ):
        return ",vflip,hflip"
    return ""


def _audio_br() -> str:
    try:
        k = int(config.get("audio_bitrate_k") or 96)
    except (TypeError, ValueError):
        k = 96
    k = max(64, min(k, 320))
    return f"{k}k"


# ── FFmpeg command builder ──────────────────────────────────────────────────

def _build_cmd(ff, single_output_path=None):
    """Build FFmpeg command for MKV segment ring-buffer or single MP4 output.

    v4.0: Uses MKV segment muxer for zero-gap ring buffer.
    MKV segments are readable mid-write (no moov atom finalization needed).
    """
    pat = os.path.join(config.TEMP_DIR, _SEG_STRFTIME)

    capture_monitors = (config.get("capture_monitors") or "primary").lower().strip()
    backend = (config.get("capture_backend") or "ddagrab").lower().strip()

    try:
        fps_i = int(config.get("fps") or 60)
    except (TypeError, ValueError):
        fps_i = 60
    fps = str(fps_i)

    try:
        max_h_i = int(config.get("capture_max_height") or 0)
    except (TypeError, ValueError):
        max_h_i = 0

    enc = encoding.resolve_encoder(ff)
    cq = str(config.get("quality"))
    venc = encoding.video_encode_args(enc, cq, fps_i)

    mon_idx = int(config.get("monitor_index") or 1)
    dda_idx = max(0, mon_idx - 1)
    draw_mouse = 1

    # Force gdigrab for all-displays mode
    if capture_monitors == "all":
        backend = "gdigrab"

    logger.info(
        "Capture: backend=%s monitors=%s output_idx=%s encoder=%s max_h=%s fps=%s",
        backend, capture_monitors, dda_idx, enc, max_h_i or "native", fps,
    )

    from audio_devices import WASAPI_IN, WASAPI_OUT

    mic = config.get("mic_device") or ""
    sys_dev = config.get("sys_audio_device") or ""

    if mic.startswith("__") and mic.endswith("__") and mic != WASAPI_IN:
        logger.warning("Unknown mic sentinel cleared: %s", mic)
        mic = ""
    if sys_dev.startswith("__") and sys_dev.endswith("__") and sys_dev != WASAPI_OUT:
        logger.warning("Unknown system-audio sentinel cleared: %s", sys_dev)
        sys_dev = ""

    audio_in = []

    # Microphone capture setup
    dshow_devs = []
    try:
        from audio_devices import list_dshow_audio
        dshow_devs = list_dshow_audio(ff)
    except Exception as _e:
        logger.warning("Could not list dshow audio devices: %s", _e)

    if mic == WASAPI_IN or (mic and mic.lower().startswith("[windows")):
        if dshow_devs:
            audio_in.append(
                ["-thread_queue_size", "4096", "-f", "dshow", "-i", f"audio={dshow_devs[0]}"]
            )
            logger.info("Microphone audio: dshow default '%s'", dshow_devs[0])
        else:
            logger.warning("No microphone device found via dshow")
    elif mic and mic != "(No microphone)":
        matched_mic = next((d for d in dshow_devs if mic.lower() in d.lower() or d.lower() in mic.lower()), None)
        if not matched_mic and dshow_devs:
            for part in mic.split():
                if len(part) >= 4 and part.lower() not in ("kulaklıklar", "headphones", "speakers", "hoparlör"):
                    matched_mic = next((d for d in dshow_devs if part.lower() in d.lower()), None)
                    if matched_mic:
                        break
        if matched_mic:
            audio_in.append(
                ["-thread_queue_size", "4096", "-f", "dshow", "-i", f"audio={matched_mic}"]
            )
            logger.info("Microphone audio matched: dshow '%s'", matched_mic)
        elif dshow_devs:
            audio_in.append(
                ["-thread_queue_size", "4096", "-f", "dshow", "-i", f"audio={dshow_devs[0]}"]
            )
            logger.info("Microphone audio fallback: dshow '%s'", dshow_devs[0])
        else:
            logger.warning("Configured mic '%s' not found in dshow input list", mic)

    # System audio capture setup (WASAPI loopback via wasapi_loopback.exe pipe)
    added_sys = False
    wasapi_exe = resolve_wasapi_exe()
    if sys_dev != "(No system audio)":
        if wasapi_exe:
            audio_in.append(
                ["-thread_queue_size", "8192",
                 "-use_wallclock_as_timestamps", "1",   # v4.0: monotonic clock sync
                 "-f", "f32le", "-ar", "48000", "-ac", "2", "-i", "pipe:0"]
            )
            added_sys = True
            logger.info("System audio: native WASAPI loopback via wasapi_loopback.exe (pipe:0)")
        elif sys_dev and sys_dev not in (WASAPI_OUT, ""):
            matched_sys = next((d for d in dshow_devs if sys_dev.lower() in d.lower() or d.lower() in sys_dev.lower()), None)
            if matched_sys:
                audio_in.append(
                    ["-thread_queue_size", "4096", "-f", "dshow", "-i", f"audio={matched_sys}"]
                )
                added_sys = True
                logger.info("System audio matched user selection: dshow '%s'", matched_sys)

    if not added_sys and sys_dev != "(No system audio)":
        _dshow_sys = _find_dshow_sys_audio(ff, exclude_mic=mic)
        if _dshow_sys:
            audio_in.append(
                ["-thread_queue_size", "4096", "-f", "dshow", "-i", f"audio={_dshow_sys}"]
            )
            added_sys = True
            logger.info("System audio fallback: dshow '%s'", _dshow_sys)
        elif dshow_devs:
            dev_to_use = next((d for d in dshow_devs if d != mic), dshow_devs[0])
            audio_in.append(
                ["-thread_queue_size", "4096", "-f", "dshow", "-i", f"audio={dev_to_use}"]
            )
            added_sys = True
            logger.info("System audio dshow fallback: '%s'", dev_to_use)

    cmd = [ff, "-y"]

    _scale = _capture_scale_filter(max_h_i)
    _flipx = _capture_flip_suffix()
    _abr = _audio_br()

    if backend == "gdigrab":
        logger.info("Capture backend: gdigrab (all displays / device input)")
        if capture_monitors == "all":
            geo = get_all_monitors_geometry()
            cmd += [
                "-thread_queue_size", "4096",
                "-probesize", "32M",
                "-analyzeduration", "0",
                "-f", "gdigrab",
                "-framerate", fps,
                "-draw_mouse", str(draw_mouse),
                "-offset_x", str(geo[0]),
                "-offset_y", str(geo[1]),
                "-video_size", f"{geo[2]}x{geo[3]}",
                "-i", "desktop",
            ]
        else:
            geo = get_monitor_geometry(mon_idx)
            cmd += [
                "-thread_queue_size", "4096",
                "-probesize", "32M",
                "-analyzeduration", "0",
                "-f", "gdigrab",
                "-framerate", fps,
                "-draw_mouse", str(draw_mouse),
                "-offset_x", str(geo[0]),
                "-offset_y", str(geo[1]),
                "-video_size", f"{geo[2]}x{geo[3]}",
                "-i", "desktop",
            ]

        for ai in audio_in:
            cmd += ai

        vconv = f"[0:v]fps={fps},{_scale}{_flipx},format=yuv420p[vout]"
        num_aud = len(audio_in)
        if num_aud == 2:
            fc = (
                f"{vconv};"
                f"[1:a]aresample=48000:async=1000:first_pts=0[a0];[2:a]aresample=48000:async=1000:first_pts=0[a1];"
                f"[a0][a1]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[aout]"
            )
            cmd += [
                "-filter_complex", fc,
                "-map", "[vout]", "-map", "[aout]",
                *venc, "-c:a", "aac", "-b:a", _abr,
            ]
        elif num_aud == 1:
            fc = f"{vconv};[1:a]aresample=48000:async=1000:first_pts=0[aout]"
            cmd += [
                "-filter_complex", fc,
                "-map", "[vout]", "-map", "[aout]",
                *venc, "-c:a", "aac", "-b:a", _abr,
            ]
        else:
            fc = vconv
            cmd += ["-filter_complex", fc, "-map", "[vout]", *venc]

    else:
        logger.info("Capture backend: ddagrab (lavfi GPU capture)")
        for ai in audio_in:
            cmd += ai

        dda_src = f"ddagrab=output_idx={dda_idx}:draw_mouse={draw_mouse}:framerate={fps},hwdownload,format=bgra"
        vconv = f"{dda_src},{_scale}{_flipx},format=yuv420p[vout]"

        num_aud = len(audio_in)
        if num_aud == 2:
            fc = (
                f"{vconv};"
                f"[0:a]aresample=48000:async=1000:first_pts=0[a0];[1:a]aresample=48000:async=1000:first_pts=0[a1];"
                f"[a0][a1]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[aout]"
            )
            cmd += [
                "-filter_complex", fc,
                "-map", "[vout]", "-map", "[aout]",
                *venc, "-c:a", "aac", "-b:a", _abr,
            ]
        elif num_aud == 1:
            fc = f"{vconv};[0:a]aresample=48000:async=1000:first_pts=0[aout]"
            cmd += [
                "-filter_complex", fc,
                "-map", "[vout]", "-map", "[aout]",
                *venc, "-c:a", "aac", "-b:a", _abr,
            ]
        else:
            fc = vconv
            cmd += ["-filter_complex", fc, "-map", "[vout]", *venc]

    if single_output_path:
        cmd += ["-movflags", "+faststart", single_output_path]
    else:
        # v4.0: MKV segment ring-buffer (segments readable mid-write)
        cmd += [
            "-f", "segment",
            "-segment_time", str(_SEGMENT_SECONDS),
            "-segment_format", "matroska",
            "-segment_format_options", "reserve_index_space=256k",
            "-reset_timestamps", "1",
            "-strftime", "1",
            pat,
        ]
    return cmd


# ── Recorder ────────────────────────────────────────────────────────────────

class Recorder:
    def __init__(self):
        self.process = None
        self.manual_proc = None
        self._wasapi_proc = None
        self.running = False
        self._lock = threading.Lock()
        os.makedirs(config.TEMP_DIR, exist_ok=True)

    # ── Start / Stop / Restart ──

    def start(self):
        with self._lock:
            if self.running:
                return
            self._launch()
            self.running = True
            threading.Thread(target=self._cleanup_loop, daemon=True).start()
            logger.info("Recording started.")

    def stop(self):
        with self._lock:
            if not self.running:
                return
            self._term()
            self.running = False
            logger.info("Recording stopped.")

    def restart(self):
        with self._lock:
            self._term()
            self._launch()
            logger.info("Recording restarted.")

    # ── Health checks ──

    def buffer_alive(self):
        """Rolling-buffer ffmpeg only (ignores manual session)."""
        return self.process is not None and self.process.poll() is None

    def is_alive(self):
        """Any active capture (buffer or manual file)."""
        if self.manual_proc is not None and self.manual_proc.poll() is None:
            return True
        return self.buffer_alive()

    def manual_recording_active(self):
        return self.manual_proc is not None and self.manual_proc.poll() is None

    def cleanup_dead_manual(self):
        """Clear handle if ffmpeg exited unexpectedly."""
        if self.manual_proc is not None and self.manual_proc.poll() is not None:
            self.manual_proc = None

    # ── Manual recording (continuous MP4) ──

    def start_manual_recording(self, out_path: str) -> bool:
        """Continuous encode to one MP4 (stops rolling-buffer process first — caller must stop it)."""
        with self._lock:
            if self.manual_proc is not None and self.manual_proc.poll() is None:
                return False
            if self.process is not None:
                logger.warning("Buffer ffmpeg still running; stop buffer before manual record")
                return False
            ff = get_ffmpeg_path()
            cmd = _build_cmd(ff, single_output_path=out_path)
            logger.info("ffmpeg manual cmd: %s", " ".join(cmd))
            try:
                err = open(
                    os.path.join(config.APPDATA_DIR, "ffmpeg_manual_stderr.log"),
                    "w", encoding="utf-8", errors="replace",
                )
            except Exception:
                err = subprocess.DEVNULL
            try:
                self.manual_proc = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=err,
                    creationflags=subprocess.CREATE_NO_WINDOW | 0x00004000,
                )
            except Exception as e:
                logger.error("Manual record failed to start: %s", e)
                return False
            logger.info("Manual recording PID=%s -> %s", self.manual_proc.pid, out_path)
            return True

    def stop_manual_recording(self):
        with self._lock:
            if self.manual_proc is None:
                return
            if self.manual_proc.poll() is None:
                try:
                    self.manual_proc.stdin.write(b"q\n")
                    self.manual_proc.stdin.flush()
                    self.manual_proc.wait(timeout=15)
                except Exception:
                    try:
                        self.manual_proc.kill()
                    except Exception:
                        pass
            self.manual_proc = None
            logger.info("Manual recording stopped.")

    # ── Internal: launch / terminate ──

    def _launch(self):
        _kill_stale_ffmpeg()
        if hasattr(self, "_wasapi_proc") and self._wasapi_proc:
            try:
                self._wasapi_proc.kill()
            except Exception:
                pass
            self._wasapi_proc = None

        sys_dev = config.get("sys_audio_device") or ""
        wasapi_exe = resolve_wasapi_exe()
        stdin_src = subprocess.PIPE

        if sys_dev != "(No system audio)" and wasapi_exe:
            try:
                self._wasapi_proc = subprocess.Popen(
                    [wasapi_exe],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                stdin_src = self._wasapi_proc.stdout
                logger.info("Started WASAPI Loopback process PID=%s", self._wasapi_proc.pid)
            except Exception as _e:
                logger.warning("Could not start WASAPI Loopback process: %s", _e)
                self._wasapi_proc = None

        ff = get_ffmpeg_path()
        cmd = _build_cmd(ff, single_output_path=None)
        logger.info("ffmpeg cmd: %s", " ".join(cmd))
        try:
            stderr_log = open(
                os.path.join(config.APPDATA_DIR, "ffmpeg_stderr.log"),
                "w", encoding="utf-8", errors="replace",
            )
        except Exception:
            stderr_log = subprocess.DEVNULL
        self.process = subprocess.Popen(
            cmd,
            stdin=stdin_src,
            stdout=subprocess.DEVNULL,
            stderr=stderr_log,
            creationflags=subprocess.CREATE_NO_WINDOW | 0x00004000,
        )
        try:
            with open(_PID_FILE, "w") as f:
                f.write(str(self.process.pid))
        except Exception:
            pass
        logger.info("ffmpeg PID=%s", self.process.pid)

    def _term(self):
        if hasattr(self, "_wasapi_proc") and self._wasapi_proc:
            try:
                self._wasapi_proc.kill()
            except Exception:
                pass
            self._wasapi_proc = None
        if self.process is None:
            return
        if self.process.poll() is None:
            try:
                self.process.stdin.write(b"q\n")
                self.process.stdin.flush()
                self.process.wait(timeout=8)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
        self.process = None
        try:
            os.remove(_PID_FILE)
        except Exception:
            pass

    # ── Segment access (v4.0: MKV segments) ──

    def _list_segments(self) -> list[str]:
        """Return all ring buffer segments sorted by mtime (oldest first)."""
        return sorted(
            glob.glob(os.path.join(config.TEMP_DIR, _SEG_PATTERN)),
            key=os.path.getmtime,
        )

    def _active_segment(self) -> str | None:
        """The currently-being-written segment (last by mtime)."""
        segs = self._list_segments()
        return segs[-1] if segs else None

    def _closed_segments(self) -> list[str]:
        """All segments except the active (currently-being-written) one."""
        segs = self._list_segments()
        if len(segs) <= 1:
            return []
        return segs[:-1]

    def reset_buffer(self):
        removed = 0
        for f in glob.glob(os.path.join(config.TEMP_DIR, _SEG_PATTERN)):
            try:
                os.remove(f)
                removed += 1
            except Exception as e:
                logger.warning("Could not remove segment %s: %s", f, e)
        # Also clean any leftover MP4 segments from old version
        for f in glob.glob(os.path.join(config.TEMP_DIR, "seg_*.mp4")):
            try:
                os.remove(f)
            except Exception:
                pass
        logger.info("Buffer cleared (%s segments removed)", removed)

    def get_segments_for_export(self, minutes=None):
        """v4.0: Non-blocking export — FFmpeg keeps running.

        Returns list of segment paths (MKV) covering the last `minutes`.
        Includes a live-copy of the active segment for zero-gap coverage.
        """
        if self.manual_proc is not None and self.manual_proc.poll() is None:
            logger.warning("get_segments_for_export: skipped (manual recording active)")
            return []
        if minutes is None:
            minutes = config.get("buffer_minutes")
        cutoff = time.time() - (minutes * 60 + 5)

        all_segs = self._list_segments()
        if not all_segs:
            return []

        # Closed segments within time window
        result = []
        active = all_segs[-1] if all_segs else None

        for s in all_segs[:-1]:  # all except active
            try:
                if os.path.getmtime(s) >= cutoff and os.path.getsize(s) >= _TAIL_MIN_BYTES:
                    result.append(s)
            except OSError:
                continue

        # Live-copy the active segment (MKV is readable mid-write)
        if active:
            tail = self._copy_active_segment(active)
            if tail:
                result.append(tail)

        logger.info("get_segments_for_export: %s segments (includes tail)", len(result))
        return result

    def _copy_active_segment(self, active_path: str) -> str | None:
        """Copy the in-progress MKV segment using FFmpeg stream copy.

        MKV segments are cluster-based and readable mid-write, unlike MP4
        which requires moov atom finalization. Windows file sharing is
        handled gracefully.
        """
        try:
            if not os.path.isfile(active_path) or os.path.getsize(active_path) < _TAIL_MIN_BYTES:
                return None
        except OSError:
            return None

        dst = os.path.join(config.TEMP_DIR, f"_tail_export_{int(time.time())}.mkv")
        try:
            ff = get_ffmpeg_path()
        except FileNotFoundError:
            ff = None

        # 1. Primary: FFmpeg stream-copy (cleanest, handles in-progress clusters on Windows)
        if ff:
            try:
                r = subprocess.run(
                    [
                        ff, "-y",
                        "-loglevel", "error",
                        "-i", active_path,
                        "-c", "copy",
                        "-f", "matroska",
                        dst,
                    ],
                    capture_output=True,
                    timeout=_TAIL_COPY_TIMEOUT,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                if r.returncode == 0 and os.path.isfile(dst) and os.path.getsize(dst) >= 2048:
                    logger.info("Active segment copied via FFmpeg: %s", os.path.basename(dst))
                    return dst
            except Exception as e:
                logger.debug("Active segment FFmpeg copy failed: %s", e)

        # 2. Secondary: Chunked binary copy with shared read
        try:
            with open(active_path, "rb") as src_f, open(dst, "wb") as dst_f:
                while True:
                    chunk = src_f.read(65536)
                    if not chunk:
                        break
                    dst_f.write(chunk)
            if os.path.isfile(dst) and os.path.getsize(dst) >= 2048:
                logger.info("Active segment chunk-copied: %s", os.path.basename(dst))
                return dst
        except Exception as e:
            logger.debug("Chunk copy failed: %s", e)

        # 3. Tertiary fallback: shutil.copy2
        try:
            shutil.copy2(active_path, dst)
            if os.path.isfile(dst) and os.path.getsize(dst) >= 2048:
                logger.info("Active segment raw-copied: %s", os.path.basename(dst))
                return dst
        except Exception as e:
            logger.debug("Raw copy also failed: %s", e)

        try:
            if os.path.isfile(dst):
                os.remove(dst)
        except OSError:
            pass
        return None

    def buffer_seconds_filled(self):
        segs = self._list_segments()
        if not segs:
            return 0
        return int(time.time() - os.path.getmtime(segs[0]))

    def estimate_capture_fps(self) -> int:
        """Approximate live capture FPS from rolling-buffer segment file timing."""
        try:
            cfg_fps = max(1, int(config.get("fps") or 30))
            segs = self._list_segments()
            if len(segs) < 2:
                return cfg_fps
            dts = []
            n = min(len(segs), 6)
            for i in range(1, n):
                dts.append(os.path.getmtime(segs[-i]) - os.path.getmtime(segs[-(i + 1)]))
            dts = [d for d in dts if d > 0.05]
            if not dts:
                return cfg_fps
            dts.sort()
            mid = dts[len(dts) // 2]
            est = int(round(cfg_fps * _SEGMENT_SECONDS / mid))
            return max(1, min(500, est))
        except Exception:
            return max(1, int(config.get("fps") or 30))

    def enable_safe_fallback(self):
        """Safe recovery mode — switch to CPU video encoding while preserving ddagrab DXGI capture."""
        logger.warning("Enabling safe capture fallback mode (CPU encoder / ddagrab)")
        config.set("capture_backend", "ddagrab")
        config.set("video_encoder", "cpu")
        config.save()

    # ── Cleanup loop (replaces old segment + game profile loops) ──

    def _cleanup_loop(self):
        """Single cleanup thread: prune segments older than buffer_minutes.

        v4.0: No game mode restart loop, no profile switching.
        """
        while self.running:
            try:
                buf_secs = config.get("buffer_minutes") * 60
                # Keep extra 30s grace for export overlap
                cutoff = time.time() - (buf_secs + 30)
                for f in glob.glob(os.path.join(config.TEMP_DIR, _SEG_PATTERN)):
                    try:
                        if os.path.getmtime(f) < cutoff:
                            os.remove(f)
                    except Exception:
                        pass
                # Also clean leftover tail copies
                for f in glob.glob(os.path.join(config.TEMP_DIR, "_tail_export_*.mkv")):
                    try:
                        age = time.time() - os.path.getmtime(f)
                        if age > 120:  # older than 2 minutes
                            os.remove(f)
                    except Exception:
                        pass
            except Exception as e:
                logger.debug("Cleanup loop error: %s", e)
            time.sleep(_CLEANUP_INTERVAL)

    # ── Legacy compatibility aliases ──

    def get_closed_segments_for_export(self, minutes=None):
        """Alias for backward compatibility."""
        return self.get_segments_for_export(minutes)

    def flush_and_get_segments_for_export(self, minutes=None):
        """v4.0: No longer flushes (stops) FFmpeg. Same as get_segments_for_export."""
        return self.get_segments_for_export(minutes)

    def cut_and_get_segments(self, minutes=None):
        """Legacy alias."""
        return self.get_segments_for_export(minutes)

    def try_copy_tail_segment(self) -> str | None:
        """Copy the in-progress last segment without stopping the buffer."""
        active = self._active_segment()
        if not active:
            return None
        return self._copy_active_segment(active)
