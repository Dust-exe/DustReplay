"""Video encoder selection (NVENC / AMF / CPU) for ffmpeg pipelines."""

import logging
import subprocess

import config

logger = logging.getLogger(__name__)

ENC_NVENC = "nvenc"
ENC_AMF = "amf"
ENC_CPU = "cpu"


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


def amf_smoke_test(ff_path: str) -> bool:
    """Return True if a minimal AMF encode succeeds (AMD GPU present)."""
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
                "h264_amf",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            timeout=25,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        if r.returncode != 0:
            logger.info("AMF smoke test failed (exit %s)", r.returncode)
        return r.returncode == 0
    except Exception as e:
        logger.debug("AMF probe error: %s", e)
        return False


def resolve_encoder(ff_path: str) -> str:
    """Resolve config video_encoder: auto | nvenc | amf | cpu."""
    mode = (config.get("video_encoder") or "auto").lower()
    if mode in ("cpu", "libx264", "x264"):
        return ENC_CPU
    if mode in ("nvenc", "nvidia", "gpu", "h264_nvenc"):
        return ENC_NVENC if nvenc_smoke_test(ff_path) else ENC_CPU
    if mode in ("amf", "amd", "h264_amf"):
        return ENC_AMF if amf_smoke_test(ff_path) else ENC_CPU
    if nvenc_smoke_test(ff_path):
        return ENC_NVENC
    if amf_smoke_test(ff_path):
        return ENC_AMF
    return ENC_CPU


def use_nvenc(ff_path: str) -> bool:
    """Backward-compatible: True when NVENC is the active encoder."""
    return resolve_encoder(ff_path) == ENC_NVENC


def video_encode_args(encoder: str, cq: str) -> list[str]:
    """ffmpeg arguments for H.264 video only (no audio)."""
    if encoder == ENC_NVENC:
        return ["-c:v", "h264_nvenc", "-preset", "p1", "-rc", "constqp", "-qp", str(cq)]
    if encoder == ENC_AMF:
        return [
            "-c:v",
            "h264_amf",
            "-usage",
            "ultralowlatency",
            "-quality",
            "speed",
            "-rc",
            "cqp",
            "-qp",
            str(cq),
        ]
    return ["-c:v", "libx264", "-preset", "ultrafast", "-crf", str(cq)]


def resolve_buffer_encoder(ff_path: str) -> str:
    """Encoder for rolling buffer: low_gpu profile forces CPU H.264."""
    profile = (config.get("buffer_encoder_profile") or "balanced").lower().strip()
    if profile == "low_gpu":
        return ENC_CPU
    return resolve_encoder(ff_path)
