import ctypes
import logging
import sys

_m = ctypes.windll.kernel32.CreateMutexW(None, False, "DustReplayMutex_v1")
if ctypes.windll.kernel32.GetLastError() == 183:
    sys.exit(0)

from logger_setup import setup_logger

setup_logger()

import keyboard
from app_window import AppWindow
import config
from first_run import ensure_ffmpeg
from recorder import Recorder
from watchdog import Watchdog

logger = logging.getLogger("main")


def main():
    logger.info("%s starting…", config.APP_DISPLAY)
    ensure_ffmpeg()
    rec = Recorder()
    app = AppWindow(rec, watchdog=None)

    def nf(title, message):
        if app._tray_icon:
            app._tray_icon.notify(message, title)

    wd = Watchdog(rec, on_notify=nf)
    app.watchdog = wd
    try:
        rec.start()
    except FileNotFoundError as e:
        ctypes.windll.user32.MessageBoxW(0, str(e), config.APP_DISPLAY, 0x10)
        sys.exit(1)
    except Exception as e:
        logger.error("Could not start capture: %s", e)
    wd.start()
    if app.overlay and config.get("overlay_enabled"):
        app.overlay.show()
    app.register_global_hotkeys()
    app.mainloop()
    keyboard.unhook_all()


if __name__ == "__main__":
    main()
