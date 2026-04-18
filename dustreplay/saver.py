import config
import encoding
import glob
import logging
import os
import subprocess
import threading
from datetime import datetime

logger = logging.getLogger(__name__)


def get_ffmpeg_path():
    p = os.path.join(config.APPDATA_DIR, "ffmpeg", "ffmpeg.exe")
    if os.path.isfile(p):
        return p
    d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg", "ffmpeg.exe")
    if os.path.isfile(d):
        return d
    return None


def save_replay(recorder, minutes=None, on_done=None, on_error=None, watchdog=None):
    threading.Thread(
        target=_worker,
        args=(recorder, minutes, on_done, on_error, watchdog),
        daemon=True,
    ).start()


def _worker(recorder, minutes, on_done, on_error, watchdog=None):
    try:
        if minutes is None:
            minutes = config.get("save_minutes")
        if watchdog:
            try:
                watchdog.set_paused(True)
            except Exception:
                pass
        segs = recorder.cut_and_get_segments(minutes)
        if watchdog:
            try:
                watchdog.set_paused(False)
            except Exception:
                pass
        if not segs:
            seg_count = len(glob.glob(os.path.join(config.TEMP_DIR, "seg_*.mp4")))
            if seg_count == 0:
                if on_error:
                    on_error("Recording has not started yet.")
                return
            if on_error:
                on_error("Wait for the first segment to finish, then try again.")
            return
        MIN_SEG = 30 * 1024
        valid_segs = [s for s in segs if os.path.getsize(s) >= MIN_SEG]
        if not valid_segs:
            if on_error:
                on_error("No valid segments to export.")
            return
        logger.info("Exporting segments %s / %s", len(valid_segs), len(segs))
        od = config.get("output_dir")
        os.makedirs(od, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        out = os.path.join(od, f"replay_{ts}.mp4")
        lp = os.path.join(od, f"_concat_{ts}.txt")
        with open(lp, "w", encoding="utf-8") as f:
            for s in valid_segs:
                f.write(f"file '{s.replace(chr(92), '/')}'\n")
        ff = get_ffmpeg_path()
        if not ff:
            if on_error:
                on_error("ffmpeg not found.")
            return
        cq = str(config.get("quality"))
        use_nvenc = encoding.use_nvenc(ff)
        venc = encoding.video_encode_args(use_nvenc, cq)
        encode_cmd = [
            ff,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            lp,
            *venc,
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            out,
        ]
        r = subprocess.run(
            encode_cmd,
            capture_output=True,
            timeout=300,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if r.returncode != 0 and use_nvenc:
            logger.warning("NVENC export failed, trying libx264…")
            venc2 = encoding.video_encode_args(False, cq)
            encode_cmd = [
                ff,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                lp,
                *venc2,
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                out,
            ]
            r = subprocess.run(
                encode_cmd,
                capture_output=True,
                timeout=300,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        try:
            os.remove(lp)
        except Exception:
            pass
        if r.returncode != 0:
            err_detail = ""
            try:
                err_detail = (
                    r.stderr.decode("utf-8", errors="replace").strip().splitlines()[-1][:80]
                )
            except Exception:
                pass
            logger.error("Merge failed (rc=%s): %s", r.returncode, err_detail)
            if on_error:
                on_error(
                    f"Merge failed: {err_detail}" if err_detail else "Merge failed."
                )
            return
        if on_done:
            on_done(out)
    except Exception as e:
        logger.exception("Save error: %s", e)
        if on_error:
            on_error(str(e))
