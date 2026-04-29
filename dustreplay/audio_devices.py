import logging
import re
import subprocess

logger = logging.getLogger(__name__)

WASAPI_IN = "__wasapi_in__"
WASAPI_OUT = "__wasapi_out__"

LABEL_NO_MIC = "(No microphone)"
LABEL_NO_SYS = "(No system audio)"
LABEL_WIN_MIC = "[Windows default input]"
LABEL_WIN_SYS = "[Windows default output loopback]"


def _run(cmd, timeout=25):
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            timeout=timeout,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except Exception as e:
        logger.warning("cmd failed %s: %s", cmd[0], e)
        return None


def _decode(data):
    for enc in ("utf-8", "utf-16-le", "mbcs", "latin-1"):
        try:
            return data.decode(enc, errors="replace")
        except Exception:
            pass
    return ""


def list_dshow_audio(ffmpeg_path):
    """DirectShow audio devices — used for microphone."""
    r = _run([ffmpeg_path, "-f", "dshow", "-list_devices", "true", "-i", "dummy"])
    if not r or (not r.stderr and not r.stdout):
        r = _run([ffmpeg_path, "-list_devices", "true", "-f", "dshow", "-i", "dummy"])
    if not r:
        return []
    text = _decode(r.stderr) + _decode(r.stdout)
    logger.info("dshow raw output length: %s", len(text))
    devs = []
    in_audio = False
    for line in text.splitlines():
        ll = line.lower()
        if "audio devices" in ll:
            in_audio = True
        elif "video devices" in ll and "audio" not in ll:
            in_audio = False
        elif in_audio and '"' in line:
            if "@device" in ll:
                continue
            m = re.search(r'"([^"]+)"', line)
            if m:
                name = m.group(1).strip()
                if name and name not in devs:
                    devs.append(name)
    if not devs:
        logger.warning("Section-based dshow parsing found nothing, trying fallback 1")
        in_video = False
        for line in text.splitlines():
            ll = line.lower()
            if "video device" in ll:
                in_video = True
            if "audio device" in ll:
                in_video = False
            if not in_video and '"' in line and "@device" not in ll:
                m = re.search(r'"([^"]{3,64})"', line)
                if m:
                    name = m.group(1).strip()
                    if name and name not in devs:
                        devs.append(name)
    if not devs:
        logger.warning("Trying error-based dshow listing (fallback 2)")
        r2 = _run([ffmpeg_path, "-f", "dshow", "-i", "audio=_OmniReplay_NoSuchDevice_"])
        if r2:
            text2 = _decode(r2.stderr) + _decode(r2.stdout)
            for line in text2.splitlines():
                ll = line.lower()
                if "@device" in ll or "could not find" in ll:
                    continue
                m = re.search(r'"([^"]{2,80})"', line)
                if m:
                    name = m.group(1).strip()
                    if name and "(" in name and name not in devs:
                        devs.append(name)
    logger.info("dshow audio devices (%s): %s", len(devs), devs)
    return devs


def list_wasapi_audio(ffmpeg_path):
    """WASAPI audio devices — prefers render/output devices for loopback."""
    r = _run([ffmpeg_path, "-f", "wasapi", "-list_devices", "true", "-i", "dummy"])
    if not r:
        return []
    text = _decode(r.stderr) + _decode(r.stdout)
    render_devs = []
    all_devs = []
    in_render = False
    for line in text.splitlines():
        ll = line.lower()
        if any(x in ll for x in ["output device", "render device", "wasapi output"]):
            in_render = True
            continue
        elif any(x in ll for x in ["input device", "capture device", "wasapi input"]):
            in_render = False
            continue
        name = None
        m = re.search(r"\[(\d+)\]\s+(.+)$", line)
        if m:
            name = re.sub(r"^\[.*?\]\s*", "", m.group(2)).strip()
        if not name:
            m = re.search(r'\d+\s*:\s*"([^"]+)"', line)
            if m:
                name = m.group(1).strip()
        if not name:
            m = re.search(r'"([^"]{3,})"', line)
            if m:
                name = m.group(1).strip()
        if name:
            name = re.sub(r"^\[.*?\]\s*", "", name).strip().strip('"').strip()
            if name and len(name) > 2 and name not in all_devs:
                all_devs.append(name)
                if in_render:
                    render_devs.append(name)
    result = render_devs if render_devs else all_devs
    logger.info("wasapi render=%s all=%s", render_devs, all_devs)
    return result


def list_all_audio(ffmpeg_path):
    """Returns (mic_items, sys_items) for UI dropdowns."""
    dshow = list_dshow_audio(ffmpeg_path)
    wasapi = list_wasapi_audio(ffmpeg_path)
    mic_items = [LABEL_NO_MIC, LABEL_WIN_MIC] + dshow
    dshow_extras = [d for d in dshow if d not in wasapi]
    sys_items = [LABEL_NO_SYS, LABEL_WIN_SYS] + wasapi + dshow_extras
    return mic_items, sys_items


def label_to_config(label, kind):
    if label in (LABEL_NO_MIC, LABEL_NO_SYS, ""):
        return ""
    if label == LABEL_WIN_MIC:
        return WASAPI_IN
    if label == LABEL_WIN_SYS:
        return WASAPI_OUT
    return label


def config_to_label(value, kind):
    if not value:
        return LABEL_NO_MIC if kind == "mic" else LABEL_NO_SYS
    if value == WASAPI_IN:
        return LABEL_WIN_MIC
    if value == WASAPI_OUT:
        return LABEL_WIN_SYS
    return value
