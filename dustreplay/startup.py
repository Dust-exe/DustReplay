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
                "highest",
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
