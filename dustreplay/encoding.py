"""Video encoder selection (NVENC vs CPU) for ffmpeg pipelines."""

import logging
import subprocess

import config

logger = logging.getLogger(__name__)


def nvenc_smoke_test(ff_path: str) -> bool:
    """Return True if a minimal NVENC encode succeeds (driver + GPU present)."""
    try:
        r = subprocess.run(
            [
                ff_path,
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=256x144:d=0.03",
                "-c:v",
                "h264_nvenc",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            timeout=25,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if r.returncode != 0:
            logger.info("NVENC smoke test failed (exit %s)", r.returncode)
        return r.returncode == 0
    except Exception as e:
        logger.debug("NVENC probe error: %s", e)
        return False


def use_nvenc(ff_path: str) -> bool:
    """Resolve config video_encoder: auto | nvenc | cpu."""
    mode = (config.get("video_encoder") or "auto").lower()
    if mode in ("cpu", "libx264", "x264"):
        return False
    if mode in ("nvenc", "nvidia", "gpu", "h264_nvenc"):
        return True
    return nvenc_smoke_test(ff_path)


def video_encode_args(use_nvenc: bool, cq: str) -> list[str]:
    """ffmpeg arguments for H.264 video only (no audio)."""
    if use_nvenc:
        return ["-c:v", "h264_nvenc", "-preset", "p1", "-cq", str(cq)]
    return ["-c:v", "libx264", "-preset", "ultrafast", "-crf", str(cq)]
