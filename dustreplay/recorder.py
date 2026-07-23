from __future__ import annotations

import config
import encoding
import glob
import logging
import os
import psutil
import subprocess
import threading
import time

logger = logging.getLogger(__name__)


def get_ffmpeg_path():
    p = config.resolve_ffmpeg_exe()
    if p:
        return p
    raise FileNotFoundError(
        "ffmpeg.exe not found. Reinstall or run first-time setup again."
    )


_PID_FILE = os.path.join(config.APPDATA_DIR, "ffmpeg.pid")


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


def _find_dshow_sys_audio(ff, exclude_mic=""):
    try:
        from audio_devices import list_dshow_audio as _lda

        devs = _lda(ff)
    except Exception:
        return None
    if not devs:
        return None
    _keywords = [
        "stereo mix",
        "wave out mix",
        "what u hear",
        "cable output",
        "virtual audio cable",
        "blackhole",
        "voicemeeter output",
        "voicemeeter vaio3 output",
        "voicemeeter out b1",
        "voicemeeter out",
    ]
    dl = [(d, d.lower()) for d in devs if d != exclude_mic]
    for kw in _keywords:
        for d, dlow in dl:
            if kw in dlow:
                logger.info("dshow system-audio candidate: '%s'", d)
                return d
    return None


def _capture_scale_filter(max_h_override: int | None = None) -> str:
    """Even dimensions for yuv420p; max height caps pixels (less RAM/CPU for ffmpeg)."""
    if max_h_override is not None:
        max_h = max_h_override
    else:
        try:
            max_h = int(config.get("capture_max_height") or 0)
        except (TypeError, ValueError):
            max_h = 0
        _, _, max_h, _, _ = _runtime_capture_params()
    if (config.get("buffer_encoder_profile") or "balanced").lower() == "low_gpu":
        max_h = 540 if max_h <= 0 else min(max_h, 540)
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
        "180",
        "rotate180",
        "rotate_180",
        "both",
        "invert",
        "upside_down",
        "flip_both",
    ):
        return ",vflip,hflip"
    return ""


def _runtime_capture_params():
    """In games: keep user FPS/resolution/backend; encode on CPU so GPU stays for the game."""
    import game_detect

    backend = (config.get("capture_backend") or "ddagrab").lower().strip()
    try:
        fps = int(config.get("fps") or 20)
    except (TypeError, ValueError):
        fps = 20
    try:
        max_h = int(config.get("capture_max_height") or 0)
    except (TypeError, ValueError):
        max_h = 0
    force_cpu = False
    draw_mouse = 1
    gm = (config.get("game_mode") or "auto").lower().strip()
    in_game = False
    if gm in ("auto", "on"):
        try:
            in_game = game_detect.is_fullscreen_game_active()
        except Exception:
            in_game = False
    if gm == "on" or (gm == "auto" and in_game):
        # Do not lower FPS or resolution — clips should match user quality settings.
        # CPU H.264 avoids NVENC/AMF fighting the game for GPU time (main stutter fix).
        force_cpu = True
        logger.info(
            "Game mode: cpu_encode backend=%s fps=%s max_h=%s (in_game=%s)",
            backend,
            fps,
            max_h or "native",
            in_game,
        )
    return backend, fps, max_h, force_cpu, draw_mouse


def _capture_profile_signature() -> tuple:
    backend, fps, max_h, force_cpu, draw_mouse = _runtime_capture_params()
    return (backend, fps, max_h, force_cpu, draw_mouse)


def _audio_br() -> str:
    try:
        k = int(config.get("audio_bitrate_k") or 96)
    except (TypeError, ValueError):
        k = 96
    k = max(64, min(k, 320))
    return f"{k}k"


def _build_cmd(ff, single_output_path=None):
    """Rolling buffer (segment mux) or one continuous MP4 when single_output_path is set."""
    pat = os.path.join(config.TEMP_DIR, "seg_%Y%m%d_%H%M%S.mp4")
    backend, fps_i, max_h_i, force_cpu, draw_mouse = _runtime_capture_params()
    fps = str(fps_i)
    enc = encoding.resolve_buffer_encoder(ff)
    if force_cpu:
        enc = encoding.ENC_CPU
    cq = str(config.get("quality"))
    venc = encoding.video_encode_args(enc, cq)

    mon_idx = int(config.get("monitor_index") or 1)
    dda_idx = max(0, mon_idx - 1)
    _mh = max_h_i
    _flip = (config.get("capture_flip") or "none").lower().strip()
    logger.info(
        "Capture: backend=%s output_idx=%s (monitor_index=%s) encoder=%s max_h=%s flip=%s",
        backend,
        dda_idx,
        mon_idx,
        enc,
        _mh or "native",
        _flip or "none",
    )
    if backend == "gdigrab":
        dda_src = f"gdigrab=framerate={fps}:draw_mouse={draw_mouse}:desktop=1,format=bgra"
        logger.info("Capture backend: gdigrab")
    else:
        # Pass fps to ddagrab — capture at target rate, not full monitor refresh.
        dda_src = (
            f"ddagrab=output_idx={dda_idx}:draw_mouse={draw_mouse}:"
            f"framerate={fps},hwdownload,format=bgra"
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
    if mic == WASAPI_IN:
        try:
            from audio_devices import list_dshow_audio

            _devs = list_dshow_audio(ff)
            if _devs:
                audio_in.append(
                    ["-thread_queue_size", "2048", "-f", "dshow", "-i", f"audio={_devs[0]}"]
                )
                logger.info("Default mic: %s", _devs[0])
            else:
                logger.warning("No default microphone found; audio skipped")
        except Exception as _e:
            logger.warning("Could not list microphones: %s", _e)
    elif mic:
        audio_in.append(
            ["-thread_queue_size", "4096", "-f", "dshow", "-i", f"audio={mic}"]
        )

    if sys_dev == WASAPI_OUT:
        _wasapi_ok = False
        _wasapi_dev = ""
        try:
            from audio_devices import list_wasapi_audio as _lwa

            _wdevs = _lwa(ff)
            if _wdevs:
                _wasapi_dev = _wdevs[0]
                _wasapi_ok = True
        except Exception as _we:
            logger.debug("WASAPI list failed: %s", _we)
        if _wasapi_ok:
            audio_in.append(
                [
                    "-thread_queue_size",
                    "2048",
                    "-f",
                    "wasapi",
                    "-loopback",
                    "1",
                    "-i",
                    _wasapi_dev or "default",
                ]
            )
            logger.info("System audio: WASAPI loopback '%s'", _wasapi_dev)
        else:
            _dshow_sys = _find_dshow_sys_audio(ff, exclude_mic=mic)
            if _dshow_sys:
                audio_in.append(
                    [
                        "-thread_queue_size",
                        "4096",
                        "-f",
                        "dshow",
                        "-i",
                        f"audio={_dshow_sys}",
                    ]
                )
                logger.info("System audio: dshow fallback '%s'", _dshow_sys)
            else:
                logger.warning(
                    "System audio unavailable (no WASAPI loopback / no dshow device)"
                )
    elif sys_dev and sys_dev != mic:
        audio_in.append(
            ["-thread_queue_size", "4096", "-f", "dshow", "-i", f"audio={sys_dev}"]
        )
    elif sys_dev and sys_dev == mic:
        logger.warning("System device same as mic; skipping duplicate")

    cmd = [ff, "-y"]
    for ai in audio_in:
        cmd += ai

    n = len(audio_in)
    _scale = _capture_scale_filter(max_h_i)
    _flipx = _capture_flip_suffix()
    if backend == "gdigrab":
        vconv = f"{dda_src},fps={fps},{_scale}{_flipx},format=yuv420p[vout]"
    else:
        vconv = f"{dda_src},{_scale}{_flipx},format=yuv420p[vout]"
    _abr = _audio_br()

    if n == 2:
        fc = (
            f"{vconv};"
            f"[0:a]aresample=48000[a0];[1:a]aresample=48000[a1];"
            f"[a0][a1]amix=inputs=2:duration=longest[aout]"
        )
        cmd += [
            "-filter_complex",
            fc,
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            *venc,
            "-c:a",
            "aac",
            "-b:a",
            _abr,
        ]
    elif n == 1:
        fc = f"{vconv};" f"[0:a]aresample=48000[aout]"
        cmd += [
            "-filter_complex",
            fc,
            "-map",
            "[vout]",
            "-map",
            "[aout]",
            *venc,
            "-c:a",
            "aac",
            "-b:a",
            _abr,
        ]
    else:
        fc = vconv
        cmd += ["-filter_complex", fc, "-map", "[vout]", *venc]

    if single_output_path:
        cmd += ["-movflags", "+faststart", single_output_path]
    else:
        cmd += [
            "-f",
            "segment",
            "-segment_time",
            str(config.get("segment_seconds")),
            "-segment_format_options",
            "flush_packets=1",
            "-strftime",
            "1",
            pat,
        ]
    return cmd


class Recorder:
    def __init__(self):
        self.process = None
        self.manual_proc = None
        self.running = False
        self._lock = threading.Lock()
        self._capture_sig: tuple | None = None
        os.makedirs(config.TEMP_DIR, exist_ok=True)

    def start(self):
        with self._lock:
            if self.running:
                return
            self._launch()
            self._capture_sig = _capture_profile_signature()
            self.running = True
            threading.Thread(target=self._cloop, daemon=True).start()
            threading.Thread(target=self._game_profile_loop, daemon=True).start()
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
            self._capture_sig = _capture_profile_signature()
            logger.info("Recording restarted.")

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
                    "w",
                    encoding="utf-8",
                    errors="replace",
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

    def _launch(self):
        _kill_stale_ffmpeg()
        ff = get_ffmpeg_path()
        cmd = _build_cmd(ff, single_output_path=None)
        logger.info("ffmpeg cmd: %s", " ".join(cmd))
        try:
            stderr_log = open(
                os.path.join(config.APPDATA_DIR, "ffmpeg_stderr.log"),
                "w",
                encoding="utf-8",
                errors="replace",
            )
        except Exception:
            stderr_log = subprocess.DEVNULL
        self.process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
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

    def _game_profile_loop(self):
        while self.running:
            try:
                self._maybe_restart_for_profile()
            except Exception as e:
                logger.debug("game profile loop: %s", e)
            import game_detect
            try:
                active = game_detect.is_fullscreen_game_active()
            except Exception:
                active = False
            time.sleep(2.0 if active else 5.0)

    def _maybe_restart_for_profile(self):
        sig = _capture_profile_signature()
        if sig == self._capture_sig:
            return
        with self._lock:
            if not self.running:
                return
            logger.info("Capture profile changed — restarting ffmpeg")
            self._term()
            time.sleep(0.25)
            self._launch()
            self._capture_sig = sig

    def _wait_last_segment_stable(self, max_wait: float = 2.5) -> None:
        time.sleep(0.45)
        segs = sorted(
            glob.glob(os.path.join(config.TEMP_DIR, "seg_*.mp4")),
            key=os.path.getmtime,
        )
        if not segs:
            return
        last = segs[-1]
        prev = -1
        stable = 0
        deadline = time.time() + max_wait
        while time.time() < deadline:
            try:
                sz = os.path.getsize(last)
            except OSError:
                break
            if sz == prev and sz >= 50_000:
                stable += 1
                if stable >= 2:
                    return
            else:
                stable = 0
            prev = sz
            time.sleep(0.12)

    def _finalize_open_segment(self, wait_timeout: float = 12) -> None:
        """Send 'q' to ffmpeg so the open segment gets a valid MP4 trailer (moov)."""
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.write(b"q\n")
                self.process.stdin.flush()
                self.process.wait(timeout=wait_timeout)
            except Exception:
                try:
                    self.process.kill()
                    self.process.wait(timeout=4)
                except Exception:
                    pass
        self.process = None
        try:
            os.remove(_PID_FILE)
        except OSError:
            pass
        self._wait_last_segment_stable()

    def _term(self):
        if self.process is None:
            return
        if self.process.poll() is None:
            try:
                self.process.stdin.write(b"q\n")
                self.process.stdin.flush()
                self.process.wait(timeout=8)
            except Exception:
                self.process.kill()
        self.process = None
        try:
            os.remove(_PID_FILE)
        except Exception:
            pass

    def reset_buffer(self):
        removed = 0
        for f in glob.glob(os.path.join(config.TEMP_DIR, "seg_*.mp4")):
            try:
                os.remove(f)
                removed += 1
            except Exception as e:
                logger.warning("Could not remove segment %s: %s", f, e)
        logger.info("Buffer cleared (%s segments removed)", removed)

    def get_recent_segments(self, minutes=None):
        if minutes is None:
            minutes = config.get("buffer_minutes")
        cutoff = time.time() - (minutes * 60)
        segs = sorted(
            glob.glob(os.path.join(config.TEMP_DIR, "seg_*.mp4")),
            key=os.path.getmtime,
        )
        if segs:
            seg_dur = config.get("segment_seconds")
            age = time.time() - os.path.getmtime(segs[-1])
            if age < seg_dur:
                segs = segs[:-1]
        return [s for s in segs if os.path.getmtime(s) >= cutoff]

    _TAIL_MIN_BYTES = 50_000
    _TAIL_MIN_AGE = 3.0

    def try_copy_tail_segment(self) -> str | None:
        """Copy the in-progress last segment without stopping the buffer."""
        segs = sorted(
            glob.glob(os.path.join(config.TEMP_DIR, "seg_*.mp4")),
            key=os.path.getmtime,
        )
        if not segs:
            return None
        last = segs[-1]
        try:
            if os.path.getsize(last) < self._TAIL_MIN_BYTES:
                return None
        except OSError:
            return None
        dst = os.path.join(config.TEMP_DIR, f"_tail_export_{int(time.time())}.mp4")
        try:
            ff = get_ffmpeg_path()
        except FileNotFoundError:
            return None
        try:
            r = subprocess.run(
                [
                    ff,
                    "-y",
                    "-loglevel",
                    "error",
                    "-i",
                    last,
                    "-c",
                    "copy",
                    "-movflags",
                    "+faststart",
                    dst,
                ],
                capture_output=True,
                timeout=45,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            if r.returncode == 0 and os.path.getsize(dst) >= 2048:
                logger.info("Tail segment copied for export: %s", os.path.basename(dst))
                return dst
        except Exception as e:
            logger.debug("Tail copy failed: %s", e)
        try:
            if os.path.isfile(dst):
                os.remove(dst)
        except OSError:
            pass
        return None

    def get_closed_segments_for_export(self, minutes=None):
        """Export without stopping ffmpeg — keeps 24/7 buffer (no black gaps on save)."""
        if self.manual_proc is not None and self.manual_proc.poll() is None:
            logger.warning("get_closed_segments_for_export: skipped (manual recording active)")
            return []
        if minutes is None:
            minutes = config.get("buffer_minutes")
        cutoff = time.time() - (minutes * 60)
        segs = sorted(
            glob.glob(os.path.join(config.TEMP_DIR, "seg_*.mp4")),
            key=os.path.getmtime,
        )
        if segs:
            age = time.time() - os.path.getmtime(segs[-1])
            try:
                size = os.path.getsize(segs[-1])
            except OSError:
                size = 0
            if age < self._TAIL_MIN_AGE and size < self._TAIL_MIN_BYTES:
                segs = segs[:-1]
        result = [
            s
            for s in segs
            if os.path.getmtime(s) >= cutoff and os.path.getsize(s) >= 2048
        ]
        logger.info("get_closed_segments_for_export: %s segments", len(result))
        return result

    def flush_and_get_segments_for_export(self, minutes=None):
        """Finalize the open segment (ffmpeg quit) so export includes everything up to save."""
        if self.manual_proc is not None and self.manual_proc.poll() is None:
            logger.warning("flush_and_get_segments_for_export: skipped (manual recording active)")
            return []
        if minutes is None:
            minutes = config.get("buffer_minutes")
        cutoff = time.time() - (minutes * 60)
        resume = self.running
        with self._lock:
            if resume:
                self._finalize_open_segment()
            segs = sorted(
                glob.glob(os.path.join(config.TEMP_DIR, "seg_*.mp4")),
                key=os.path.getmtime,
            )
            result = [
                s
                for s in segs
                if os.path.getmtime(s) >= cutoff and os.path.getsize(s) >= 2048
            ]
            logger.info("flush_and_get_segments_for_export: %s segments", len(result))
            if resume:
                try:
                    self._launch()
                    self._capture_sig = _capture_profile_signature()
                    logger.info("Recording restarted after save flush.")
                except Exception as e:
                    logger.error("Failed to restart after save flush: %s", e)
        return result

    def get_segments_for_export(self, minutes=None):
        """Always flush the live segment so the last 10–30s are included in the clip."""
        return self.flush_and_get_segments_for_export(minutes)

    def cut_and_get_segments(self, minutes=None):
        return self.flush_and_get_segments_for_export(minutes)

    def buffer_seconds_filled(self):
        segs = sorted(
            glob.glob(os.path.join(config.TEMP_DIR, "seg_*.mp4")),
            key=os.path.getmtime,
        )
        if not segs:
            return 0
        return int(time.time() - os.path.getmtime(segs[0]))

    def estimate_capture_fps(self) -> int:
        """Approximate live capture FPS from rolling-buffer segment file timing."""
        try:
            cfg_fps = max(1, int(config.get("fps") or 30))
            seg_s = float(config.get("segment_seconds") or 10)
            if seg_s < 1.0:
                seg_s = 10.0
            segs = sorted(
                glob.glob(os.path.join(config.TEMP_DIR, "seg_*.mp4")),
                key=os.path.getmtime,
            )
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
            est = int(round(cfg_fps * seg_s / mid))
            return max(1, min(500, est))
        except Exception:
            return max(1, int(config.get("fps") or 30))

    def _cloop(self):
        while self.running:
            g = config.get("segment_cleanup_grace")
            c = time.time() - (config.get("buffer_minutes") * 60 + g)
            for f in glob.glob(os.path.join(config.TEMP_DIR, "seg_*.mp4")):
                try:
                    if os.path.getmtime(f) < c:
                        os.remove(f)
                except Exception:
                    pass
            time.sleep(15)
