from __future__ import annotations

import config
import encoding
import glob
import logging
import os
import subprocess
import threading
from datetime import datetime
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


def get_ffmpeg_path():
    return config.resolve_ffmpeg_exe()


def _ffprobe_path(ff: str) -> Optional[str]:
    d = os.path.dirname(ff)
    p = os.path.join(d, "ffprobe.exe")
    return p if os.path.isfile(p) else None


def _segment_has_audio(ff: str, seg_path: str) -> bool:
    prob = _ffprobe_path(ff)
    if not prob:
        return True
    try:
        r = subprocess.run(
            [
                prob,
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "csv=p=0",
                seg_path,
            ],
            capture_output=True,
            text=True,
            timeout=12,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return bool((r.stdout or "").strip())
    except Exception:
        return True


def _subprocess_flags():
    try:
        return subprocess.CREATE_NO_WINDOW
    except Exception:
        return 0


def _merge_export(ff: str, lp: str, out: str, valid_segs: list) -> Tuple[bool, str]:
    """Try stream copy first; fall back to re-encode (with or without audio)."""
    r0 = subprocess.run(
        [
            ff,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            lp,
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            out,
        ],
        capture_output=True,
        timeout=900,
        creationflags=_subprocess_flags(),
    )
    if r0.returncode == 0:
        return True, ""
    err0 = ""
    try:
        err0 = (r0.stderr or b"").decode("utf-8", errors="replace").strip()[-400:]
    except Exception:
        pass
    logger.warning("concat copy failed, re-encoding. stderr tail: %s", err0)

    cq = str(config.get("quality"))
    enc = encoding.resolve_encoder(ff)
    venc = encoding.video_encode_args(enc, cq)
    has_audio = _segment_has_audio(ff, valid_segs[0])
    try:
        abk = int(config.get("audio_bitrate_k") or 96)
    except (TypeError, ValueError):
        abk = 96
    abk = max(64, min(abk, 320))
    cmd = [
        ff,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        lp,
        *venc,
    ]
    if has_audio:
        cmd += ["-c:a", "aac", "-b:a", f"{abk}k"]
    else:
        cmd += ["-an"]
    cmd += ["-movflags", "+faststart", out]

    r = subprocess.run(
        cmd,
        capture_output=True,
        timeout=900,
        creationflags=_subprocess_flags(),
    )
    if r.returncode != 0 and enc != encoding.ENC_CPU:
        logger.warning("GPU export failed (%s), trying libx264…", enc)
        venc2 = encoding.video_encode_args(encoding.ENC_CPU, cq)
        cmd2 = [
            ff,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            lp,
            *venc2,
        ]
        if has_audio:
            cmd2 += ["-c:a", "aac", "-b:a", f"{abk}k"]
        else:
            cmd2 += ["-an"]
        cmd2 += ["-movflags", "+faststart", out]
        r = subprocess.run(
            cmd2,
            capture_output=True,
            timeout=900,
            creationflags=_subprocess_flags(),
        )
    if r.returncode != 0 and has_audio:
        logger.warning("Re-encode with audio failed; retrying video-only (-an).")
        venc3 = encoding.video_encode_args(encoding.ENC_CPU, cq)
        cmd3 = [
            ff,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            lp,
            *venc3,
            "-an",
            "-movflags",
            "+faststart",
            out,
        ]
        r = subprocess.run(
            cmd3,
            capture_output=True,
            timeout=900,
            creationflags=_subprocess_flags(),
        )
    if r.returncode != 0:
        try:
            tail = (r.stderr or b"").decode("utf-8", errors="replace").strip().splitlines()[-1][:120]
        except Exception:
            tail = ""
        return False, tail
    return True, ""


def save_replay(recorder, minutes=None, on_done=None, on_error=None, watchdog=None):
    threading.Thread(
        target=_worker,
        args=(recorder, minutes, on_done, on_error, watchdog),
        daemon=True,
    ).start()


def _worker(recorder, minutes, on_done, on_error, watchdog=None):
    try:
        if minutes is None:
            minutes = config.get("buffer_minutes")
        if watchdog:
            try:
                watchdog.set_paused(True)
            except Exception:
                pass
        segs = recorder.get_segments_for_export(minutes)
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
        MIN_SEG = 2048
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
        ok, err_detail = _merge_export(ff, lp, out, valid_segs)
        try:
            os.remove(lp)
        except Exception:
            pass
        if not ok:
            logger.error("Merge failed: %s", err_detail)
            if on_error:
                on_error(f"Merge failed: {err_detail}" if err_detail else "Merge failed.")
            return
        for s in valid_segs:
            try:
                os.remove(s)
            except Exception as e:
                logger.debug("Could not remove segment %s: %s", s, e)
        if on_done:
            on_done(out)
    except Exception as e:
        logger.exception("Save error: %s", e)
        if on_error:
            on_error(str(e))
