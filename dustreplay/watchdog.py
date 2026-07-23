import logging
import threading
import time

import config
from config import APP_DISPLAY

logger = logging.getLogger(__name__)


class Watchdog:
    def __init__(self, recorder, on_notify=None):
        self.recorder = recorder
        self.on_notify = on_notify
        self._cc = 0
        self._running = False
        self._paused = False
        self._notified = False

    def start(self):
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._running = False

    def set_paused(self, p):
        self._paused = p

    def _loop(self):
        while self._running:
            time.sleep(config.get("watchdog_interval") or 3.0)
            if self._paused:
                continue
            if not self.recorder.buffer_alive():
                self._cc += 1
                logger.warning("ffmpeg died (%sx)", self._cc)

                if self._cc >= (config.get("max_crash_count") or 3):
                    if not self._notified and self.on_notify:
                        self.on_notify(
                            APP_DISPLAY,
                            "Kayıt kurtarıldı (Güvenli moda geçildi).",
                        )
                        self._notified = True

                    # Switch to safe fallback mode in recorder
                    try:
                        if hasattr(self.recorder, "enable_safe_fallback"):
                            self.recorder.enable_safe_fallback()
                    except Exception as e:
                        logger.error("Safe fallback error: %s", e)

                time.sleep(config.get("crash_restart_delay") or 3.0)
                try:
                    self.recorder.restart()
                except Exception as e:
                    logger.error("Restart error: %s", e)
            elif self._cc > 0:
                self._cc = max(0, self._cc - 1)
                if self._cc == 0:
                    self._notified = False
