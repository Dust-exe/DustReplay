import json
import logging
import os

logger = logging.getLogger(__name__)

APP_NAME = "OmniReplay"
APP_DISPLAY = "Omni Replay"
APPDATA_DIR = os.path.join(os.getenv("APPDATA", os.path.expanduser("~")), APP_NAME)
TEMP_DIR = os.path.join(APPDATA_DIR, "temp")
LOG_DIR = APPDATA_DIR
_CFG_FILE = os.path.join(APPDATA_DIR, "settings.json")

_DEFAULTS = {
    "buffer_minutes": 20,
    "segment_seconds": 10,
    "fps": 30,
    "quality": 28,
    "video_encoder": "auto",
    "monitor_index": 1,
    "mic_device": "",
    "sys_audio_device": "__wasapi_out__",
    "hotkey_save": "f9",
    "hotkey_toggle": "f10",
    "panel_hotkey": "alt+c",
    "panel_side": "right",
    "output_dir": os.path.join(os.path.expanduser("~"), "Videos", APP_NAME),
    "watchdog_interval": 5,
    "max_crash_count": 10,
    "crash_restart_delay": 3,
    "segment_cleanup_grace": 90,
    "overlay_enabled": True,
    "overlay_x": 20,
    "overlay_y": 20,
    "overlay_monitor": 0,
    "stats_show_cpu": True,
    "stats_show_ram": True,
    "stats_show_gpu": True,
    "stats_overlay_corner": "br",
    "stats_overlay_x": None,
    "stats_overlay_y": None,
    "stats_overlay_alpha": 0.78,
    "stats_overlay_mode": "normal",
    "stats_show_fps": True,
    "ui_language": "en",
}

_cfg = {}


def load():
    global _cfg
    _cfg = dict(_DEFAULTS)
    os.makedirs(APPDATA_DIR, exist_ok=True)
    if os.path.isfile(_CFG_FILE):
        try:
            with open(_CFG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            _cfg.update({k: saved[k] for k in _DEFAULTS if k in saved})
        except Exception as e:
            logger.warning("Could not read settings: %s", e)


def save():
    os.makedirs(APPDATA_DIR, exist_ok=True)
    try:
        with open(_CFG_FILE, "w", encoding="utf-8") as f:
            json.dump(_cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error("Could not save settings: %s", e)


def get(key):
    return _cfg.get(key, _DEFAULTS.get(key))


def set(key, value):
    _cfg[key] = value


def migrate():
    """Normalize legacy settings from older single-file builds."""
    changed = False
    for key in ("mic_device", "sys_audio_device"):
        v = _cfg.get(key, "")
        if v and v.startswith("__") and v.endswith("__"):
            if key == "mic_device" and v != "__wasapi_in__":
                _cfg[key] = ""
                changed = True
            elif key == "sys_audio_device" and v != "__wasapi_out__":
                _cfg[key] = ""
                changed = True
    if not _cfg.get("sys_audio_device"):
        _cfg["sys_audio_device"] = "__wasapi_out__"
        changed = True
    if _cfg.get("segment_seconds", 10) > 15:
        _cfg["segment_seconds"] = 10
        changed = True
    if int(_cfg.get("monitor_index") or 1) < 1:
        _cfg["monitor_index"] = 1
        changed = True
    if "video_encoder" not in _cfg:
        _cfg["video_encoder"] = "auto"
        changed = True
    if "stats_overlay_corner" not in _cfg:
        _cfg["stats_overlay_corner"] = "br"
        changed = True
    if "stats_show_fps" not in _cfg:
        _cfg["stats_show_fps"] = True
        changed = True
    if "stats_overlay_mode" not in _cfg:
        _cfg["stats_overlay_mode"] = "normal"
        changed = True
    if changed:
        try:
            save()
        except Exception:
            pass


load()
migrate()
