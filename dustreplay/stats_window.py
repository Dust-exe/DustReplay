"""Live system / capture stats (optional metrics from Settings)."""

import logging
import os
import time

import customtkinter as ctk

import config

logger = logging.getLogger(__name__)

try:
    import psutil
except ImportError:
    psutil = None


class StatsWindow(ctk.CTkToplevel):
    def __init__(self, master, recorder, app_ref):
        super().__init__(master)
        self.recorder = recorder
        self._app = app_ref
        self.title("DustReplay — Live stats")
        self.geometry("320x420")
        self.configure(fg_color="#08080e")
        self.attributes("-topmost", True)
        self.resizable(False, False)

        ctk.CTkLabel(
            self,
            text="Live statistics",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color="#9933ff",
        ).pack(pady=(14, 8))

        self._body = ctk.CTkScrollableFrame(self, fg_color="#0d0d14", corner_radius=8)
        self._body.pack(fill="both", expand=True, padx=12, pady=(0, 12))

        ctk.CTkButton(
            self,
            text="Close",
            command=self.destroy,
            fg_color="#2a004a",
            hover_color="#6622cc",
            width=120,
        ).pack(pady=(0, 10))

        self._labels = {}
        self._tick_id = None
        self._enc_probe = None
        self._enc_probe_at = 0.0
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self._schedule_tick()

    def _schedule_tick(self):
        self._refresh()
        self._tick_id = self.after(900, self._schedule_tick)

    def destroy(self):
        if self._tick_id:
            try:
                self.after_cancel(self._tick_id)
            except Exception:
                pass
            self._tick_id = None
        super().destroy()

    def _refresh(self):
        if not self.winfo_exists():
            return
        lines = []

        def add(key, title, value):
            if not config.get(key):
                return
            lines.append((title, value))

        fps = str(config.get("fps"))
        mon = int(config.get("monitor_index") or 1)
        buf = self.recorder.buffer_seconds_filled()
        bmax = int(config.get("buffer_minutes") or 1) * 60
        buf_pct = min(100, int(100 * buf / bmax)) if bmax else 0

        add("stats_show_target_fps", "Target capture FPS", fps)
        add("stats_show_display", "Display index", str(mon))

        if config.get("stats_show_encoder"):
            mode = (config.get("video_encoder") or "auto").lower()
            enc_line = f"Setting: {mode}"
            now = time.time()
            if now - self._enc_probe_at > 25:
                self._enc_probe_at = now
                try:
                    import encoding

                    ff = os.path.join(config.APPDATA_DIR, "ffmpeg", "ffmpeg.exe")
                    if os.path.isfile(ff):
                        self._enc_probe = (
                            "NVENC" if encoding.use_nvenc(ff) else "CPU (libx264)"
                        )
                    else:
                        self._enc_probe = "?"
                except Exception:
                    self._enc_probe = "?"
            if self._enc_probe:
                enc_line += f"  → pipeline: {self._enc_probe}"
            lines.append(("Video encoder", enc_line))

        add(
            "stats_show_buffer",
            "Buffer fill",
            f"{buf // 60}:{buf % 60:02d} / {bmax // 60}:{bmax % 60:02d}  ({buf_pct}%)",
        )

        alive = self.recorder.is_alive()
        manual = self.recorder.manual_recording_active()
        state = (
            "Manual file recording"
            if manual
            else ("Rolling buffer ON" if alive else "Capture OFF")
        )
        add("stats_show_capture_state", "Capture", state)

        if psutil:
            try:
                add(
                    "stats_show_cpu",
                    "CPU usage",
                    f"{psutil.cpu_percent(interval=None):.0f}%",
                )
                vm = psutil.virtual_memory()
                add(
                    "stats_show_ram",
                    "RAM usage",
                    f"{vm.percent:.0f}%  ({vm.used // (1024**3)} / {vm.total // (1024**3)} GiB)",
                )
                du = psutil.disk_usage(os.path.splitdrive(config.get("output_dir") or "C:")[0] + "\\")
                add(
                    "stats_show_disk",
                    "Disk free (output drive)",
                    f"{du.free // (1024**3)} GiB free",
                )
            except Exception as e:
                logger.debug("psutil read: %s", e)
        else:
            if config.get("stats_show_cpu") or config.get("stats_show_ram"):
                lines.append(("psutil", "Install psutil for CPU/RAM (pip install psutil)"))

        add("stats_show_uptime", "App uptime (approx)", f"{int(time.time() - self._app._start_time)} s")

        for w in self._body.winfo_children():
            w.destroy()

        for title, value in lines:
            fr = ctk.CTkFrame(self._body, fg_color="#151520", corner_radius=6)
            fr.pack(fill="x", pady=4, padx=4)
            ctk.CTkLabel(
                fr,
                text=title,
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color="#aa88dd",
                anchor="w",
            ).pack(anchor="w", padx=10, pady=(6, 0))
            ctk.CTkLabel(
                fr,
                text=value,
                font=ctk.CTkFont(size=12),
                text_color="#e8e8f0",
                anchor="w",
                wraplength=280,
            ).pack(anchor="w", padx=10, pady=(0, 8))

        if not lines:
            ctk.CTkLabel(
                self._body,
                text="No metrics enabled.\nOpen Settings → Live statistics.",
                text_color="#666688",
            ).pack(pady=20)
