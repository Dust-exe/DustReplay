import logging
import threading
import time

import config

logger = logging.getLogger(__name__)


class Watchdog:
    def __init__(self, recorder, on_notify=None):
        self.recorder = recorder
        self.on_notify = on_notify
        self._cc = 0
        self._running = False
        self._paused = False

    def start(self):
        self._running = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._running = False

    def set_paused(self, p):
        self._paused = p

    def _loop(self):
        while self._running:
            time.sleep(config.get("watchdog_interval"))
            if self._paused:
                continue
            if not self.recorder.buffer_alive():
                self._cc += 1
                logger.warning("ffmpeg died (%sx)", self._cc)
                if self._cc >= config.get("max_crash_count") and self.on_notify:
                    self.on_notify(
                        "DustReplay",
                        f"ffmpeg crashed {self._cc} times. Check logs.",
                    )
                time.sleep(config.get("crash_restart_delay"))
                try:
                    self.recorder.restart()
                except Exception as e:
                    logger.error("Restart error: %s", e)
            elif self._cc > 0:
                self._cc = max(0, self._cc - 1)
