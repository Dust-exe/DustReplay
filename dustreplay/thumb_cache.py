"""JPEG thumbnails for gallery rows (ffmpeg frame grab)."""

from __future__ import annotations

import hashlib
import logging
import os
import subprocess
import threading

import config

logger = logging.getLogger(__name__)

_THUMB_W = 200


def _cache_path(fp: str) -> str:
    try:
        st = os.stat(fp)
        raw = f"{os.path.abspath(fp)}\0{st.st_mtime_ns}\0{st.st_size}".encode("utf-8", errors="replace")
    except OSError:
        raw = fp.encode("utf-8", errors="replace")
    h = hashlib.sha256(raw).hexdigest()[:24]
    d = os.path.join(config.APPDATA_DIR, "thumbnails")
    return os.path.join(d, f"{h}.jpg")


def _flags():
    try:
        return subprocess.CREATE_NO_WINDOW
    except Exception:
        return 0


import concurrent.futures

_thumb_pool = concurrent.futures.ThreadPoolExecutor(max_workers=2)


def ensure_thumb_jpeg(fp: str, master, on_path) -> None:
    """Call on_path(jpeg_path) on Tk thread when ready (master.after)."""

    def work():
        out = _cache_path(fp)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        try:
            if os.path.isfile(out):
                try:
                    if os.path.getmtime(out) >= os.path.getmtime(fp):
                        return out
                except OSError:
                    pass
        except Exception:
            pass
        ff = config.resolve_ffmpeg_exe()
        if not ff:
            return None
        vf = f"scale={_THUMB_W}:-2:flags=bicubic"
        cmd = [
            ff,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            "0.35",
            "-i",
            fp,
            "-frames:v",
            "1",
            "-vf",
            vf,
            "-q:v",
            "5",
            out,
        ]
        try:
            r = subprocess.run(
                cmd,
                capture_output=True,
                timeout=45,
                creationflags=_flags(),
            )
            if r.returncode != 0 or not os.path.isfile(out):
                return None
            return out
        except Exception as e:
            logger.debug("thumb ffmpeg: %s", e)
            return None

    def run():
        path = work()
        if not path:
            return

        def deliver():
            try:
                on_path(path)
            except Exception:
                pass

        try:
            if master is not None:
                master.after(0, deliver)
            else:
                deliver()
        except Exception:
            deliver()

    _thumb_pool.submit(run)
