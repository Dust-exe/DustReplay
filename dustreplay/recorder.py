import config
import encoding
import glob
import logging
import os
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
        subprocess.run(
            ["taskkill", "/F", "/PID", str(old_pid)],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        logger.info("Terminated stale ffmpeg PID=%s", old_pid)
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


def _build_cmd(ff, single_output_path=None):
    """Rolling buffer (segment mux) or one continuous MP4 when single_output_path is set."""
    pat = os.path.join(config.TEMP_DIR, "seg_%Y%m%d_%H%M%S.mp4")
    fps = str(config.get("fps"))
    use_nvenc = encoding.use_nvenc(ff)
    cq = str(config.get("quality"))
    venc = encoding.video_encode_args(use_nvenc, cq)

    mon_idx = int(config.get("monitor_index") or 1)
    dda_idx = max(0, mon_idx - 1)
    logger.info(
        "Capture: ddagrab output_idx=%s (monitor_index=%s) nvenc=%s",
        dda_idx,
        mon_idx,
        use_nvenc,
    )
    dda_src = f"ddagrab=output_idx={dda_idx}:draw_mouse=1,hwdownload,format=bgra"

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
                    ["-thread_queue_size", "4096", "-f", "dshow", "-i", f"audio={_devs[0]}"]
                )
                logger.info("Default mic: %s", _devs[0])
            else:
                logger.warning("No default microphone found; audio skipped")
        except Exception as _e:
            logger.warning("Could not list microphones: %s", _e)
    elif mic:
        audio_in.append(
            ["-thread_queue_size", "8192", "-f", "dshow", "-i", f"audio={mic}"]
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
                    "4096",
                    "-f",
                    "wasapi",
                    "-loopback",
                    "-i",
                    _wasapi_dev,
                ]
            )
            logger.info("System audio: WASAPI loopback '%s'", _wasapi_dev)
        else:
            _dshow_sys = _find_dshow_sys_audio(ff, exclude_mic=mic)
            if _dshow_sys:
                audio_in.append(
                    [
                        "-thread_queue_size",
                        "8192",
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
            ["-thread_queue_size", "8192", "-f", "dshow", "-i", f"audio={sys_dev}"]
        )
    elif sys_dev and sys_dev == mic:
        logger.warning("System device same as mic; skipping duplicate")

    cmd = [ff, "-y"]
    for ai in audio_in:
        cmd += ai

    n = len(audio_in)
    vconv = (
        f"{dda_src},fps={fps},scale=trunc(iw/2)*2:trunc(ih/2)*2,format=yuv420p[vout]"
    )

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
            "128k",
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
            "128k",
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
            "-strftime",
            "1",
            "-reset_timestamps",
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
        os.makedirs(config.TEMP_DIR, exist_ok=True)

    def start(self):
        with self._lock:
            if self.running:
                return
            self._launch()
            self.running = True
            threading.Thread(target=self._cloop, daemon=True).start()
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
                    creationflags=subprocess.CREATE_NO_WINDOW,
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
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        try:
            with open(_PID_FILE, "w") as f:
                f.write(str(self.process.pid))
        except Exception:
            pass
        logger.info("ffmpeg PID=%s", self.process.pid)

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

    def cut_and_get_segments(self, minutes=None):
        if self.manual_proc is not None and self.manual_proc.poll() is None:
            logger.warning("cut_and_get_segments: skipped (manual recording active)")
            return []
        if minutes is None:
            minutes = config.get("buffer_minutes")
        cutoff = time.time() - (minutes * 60)
        with self._lock:
            if self.process and self.process.poll() is None:
                try:
                    self.process.stdin.write(b"q\n")
                    self.process.stdin.flush()
                    self.process.wait(timeout=6)
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
            time.sleep(0.35)
            segs = sorted(
                glob.glob(os.path.join(config.TEMP_DIR, "seg_*.mp4")),
                key=os.path.getmtime,
            )
            result = [s for s in segs if os.path.getmtime(s) >= cutoff]
            logger.info("cut_and_get_segments: %s segments", len(result))
            try:
                self._launch()
                logger.info("Recording restarted after cut.")
            except Exception as e:
                logger.error("Failed to restart after cut: %s", e)
        return result

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
