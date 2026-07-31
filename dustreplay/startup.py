import logging
import os
import subprocess
import sys

logger = logging.getLogger(__name__)

TASK_NAME = "DustReplay"


def _exe():
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")


def is_registered():
    try:
        return (
            subprocess.run(
                ["schtasks", "/query", "/tn", TASK_NAME],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            ).returncode
            == 0
        )
    except Exception:
        return False


def register():
    try:
        subprocess.run(
            [
                "schtasks",
                "/create",
                "/tn",
                TASK_NAME,
                "/tr",
                f'"{_exe()}"',
                "/sc",
                "onlogon",
                "/rl",
                "limited",
                "/f",
            ],
            check=True,
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return True
    except Exception:
        return False


def unregister():
    try:
        subprocess.run(
            ["schtasks", "/delete", "/tn", TASK_NAME, "/f"],
            check=True,
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        return True
    except Exception:
        return False


def clean_update_data():
    """Wipe temp files, thumbs, and stale logs on version update while keeping settings.json."""
    import shutil
    import config
    import version

    ver_file = os.path.join(config.APPDATA_DIR, "last_version.txt")
    current_ver = getattr(version, "__version__", "3.8.6")
    last_ver = ""
    if os.path.isfile(ver_file):
        try:
            with open(ver_file, "r", encoding="utf-8") as f:
                last_ver = f.read().strip()
        except Exception:
            pass

    if last_ver != current_ver:
        logger.info("Version update detected (%s -> %s). Performing clean reset of temp & cache...", last_ver or "old", current_ver)
        
        # Wipe temp folder
        temp_dir = os.path.join(config.APPDATA_DIR, "temp")
        if os.path.isdir(temp_dir):
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
                os.makedirs(temp_dir, exist_ok=True)
            except Exception as e:
                logger.warning("Could not clear temp dir: %s", e)

        # Wipe thumbs folder
        thumbs_dir = os.path.join(config.APPDATA_DIR, "thumbs")
        if os.path.isdir(thumbs_dir):
            try:
                shutil.rmtree(thumbs_dir, ignore_errors=True)
                os.makedirs(thumbs_dir, exist_ok=True)
            except Exception as e:
                logger.warning("Could not clear thumbs dir: %s", e)

        # Wipe stale logs
        for log_name in ("ffmpeg_stderr.log", "app.log"):
            lp = os.path.join(config.APPDATA_DIR, log_name)
            if os.path.isfile(lp):
                try:
                    os.remove(lp)
                except Exception:
                    pass

        try:
            with open(ver_file, "w", encoding="utf-8") as f:
                f.write(current_ver)
            logger.info("Clean update reset completed for v%s. Settings preserved.", current_ver)
        except Exception as e:
            logger.warning("Could not write last_version.txt: %s", e)
