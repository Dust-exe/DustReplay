"""Frameless semi-transparent hardware overlay (CPU / RAM / GPU)."""

from __future__ import annotations

import logging
import subprocess
import sys
import time

import customtkinter as ctk

import config

logger = logging.getLogger(__name__)

try:
    import psutil
except ImportError:
    psutil = None

_BG = "#0a0612"
_FG = "#e8e0ff"
_AC = "#aa77ff"


def _subprocess_flags():
    if sys.platform == "win32":
        try:
            return subprocess.CREATE_NO_WINDOW
        except Exception:
            pass
    return 0


def _query_nvidia_gpu() -> str | None:
    try:
        r = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=2,
            creationflags=_subprocess_flags(),
        )
        if r.returncode != 0 or not (r.stdout or "").strip():
            return None
        line = (r.stdout or "").strip().splitlines()[0].strip()
        pct = float(line)
        return f"{int(round(pct))}%"
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.debug("nvidia-smi: %s", e)
        return None


class StatsWindow(ctk.CTkToplevel):
    """Borderless, draggable, topmost overlay with live CPU / RAM / GPU."""

    _W = 216
    _H = 118

    def __init__(self, master, recorder, app_ref):
        super().__init__(master)
        self.recorder = recorder
        self._app = app_ref
        self._tick_id = None
        self._gpu_cache = ""
        self._gpu_cache_at = 0.0
        self._drag_offset = None

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        try:
            a = float(config.get("stats_overlay_alpha") or 0.88)
            a = max(0.35, min(1.0, a))
        except Exception:
            a = 0.88
        self.attributes("-alpha", a)

        self.configure(fg_color=_BG)
        self.resizable(False, False)
        self.minsize(self._W, self._H)
        self.maxsize(self._W, self._H)

        self._place_initial_geometry()

        outer = ctk.CTkFrame(self, fg_color=_BG, corner_radius=10)
        outer.pack(fill="both", expand=True, padx=2, pady=2)

        hdr = ctk.CTkFrame(outer, fg_color="transparent", height=22)
        hdr.pack(fill="x", padx=6, pady=(6, 2))
        hdr.pack_propagate(False)

        self._hdr_title = ctk.CTkLabel(
            hdr,
            text="Hardware",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=_AC,
            anchor="w",
        )
        self._hdr_title.pack(side="left")

        ctk.CTkButton(
            hdr,
            text="\u2715",
            width=22,
            height=20,
            font=ctk.CTkFont(size=12),
            fg_color="#2a1030",
            hover_color="#552266",
            corner_radius=4,
            command=self._close,
        ).pack(side="right")

        self._body = ctk.CTkFrame(outer, fg_color="transparent")
        self._body.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._lbl_cpu = self._metric_row(0, "CPU")
        self._lbl_ram = self._metric_row(1, "RAM")
        self._lbl_gpu = self._metric_row(2, "GPU")

        for w in (outer, self._body, hdr, self._hdr_title):
            w.bind("<ButtonPress-1>", self._on_drag_start)
            w.bind("<B1-Motion>", self._on_drag_motion)
            w.bind("<ButtonRelease-1>", self._on_drag_end)

        self.protocol("WM_DELETE_WINDOW", self._close)
        self._schedule_tick()

    def _metric_row(self, row: int, name: str):
        fr = ctk.CTkFrame(self._body, fg_color="transparent")
        fr.grid(row=row, column=0, sticky="ew", pady=2)
        self._body.grid_columnconfigure(0, weight=1)
        nm = ctk.CTkLabel(
            fr,
            text=name,
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=_FG,
            width=40,
            anchor="w",
        )
        nm.pack(side="left")
        val = ctk.CTkLabel(
            fr,
            text="--",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=_AC,
            anchor="e",
        )
        val.pack(side="right", fill="x", expand=True)
        for w in (fr, nm, val):
            w.bind("<ButtonPress-1>", self._on_drag_start)
            w.bind("<B1-Motion>", self._on_drag_motion)
            w.bind("<ButtonRelease-1>", self._on_drag_end)
        return val

    def _place_initial_geometry(self):
        x = config.get("stats_overlay_x")
        y = config.get("stats_overlay_y")
        try:
            self.update_idletasks()
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            if x is None or y is None:
                gx = sw - self._W - 20
                gy = sh - self._H - 96
            else:
                gx = int(x)
                gy = int(y)
            gx = max(0, min(gx, max(0, sw - self._W)))
            gy = max(0, min(gy, max(0, sh - self._H)))
            self.geometry(f"{self._W}x{self._H}+{gx}+{gy}")
        except Exception:
            self.geometry(f"{self._W}x{self._H}+40+40")

    def _on_drag_start(self, event):
        self._drag_offset = (event.x_root - self.winfo_x(), event.y_root - self.winfo_y())

    def _on_drag_motion(self, event):
        if not self._drag_offset:
            return
        ox, oy = self._drag_offset
        nx = event.x_root - ox
        ny = event.y_root - oy
        self.geometry(f"{self._W}x{self._H}+{nx}+{ny}")

    def _on_drag_end(self, event):
        self._drag_offset = None
        try:
            config.set("stats_overlay_x", self.winfo_x())
            config.set("stats_overlay_y", self.winfo_y())
            config.save()
        except Exception as e:
            logger.debug("stats overlay pos save: %s", e)

    def _close(self):
        try:
            config.set("stats_overlay_x", self.winfo_x())
            config.set("stats_overlay_y", self.winfo_y())
            config.save()
        except Exception:
            pass
        self.destroy()

    def _schedule_tick(self):
        self._refresh()
        self._tick_id = self.after(1000, self._schedule_tick)

    def destroy(self):
        if self._tick_id:
            try:
                self.after_cancel(self._tick_id)
            except Exception:
                pass
            self._tick_id = None
        super().destroy()

    def _gpu_text(self) -> str:
        if not config.get("stats_show_gpu"):
            return ""
        now = time.time()
        if now - self._gpu_cache_at < 1.5 and self._gpu_cache:
            return self._gpu_cache
        g = _query_nvidia_gpu()
        self._gpu_cache_at = now
        if g:
            self._gpu_cache = g
            return g
        self._gpu_cache = "--"
        return "--"

    def _refresh(self):
        if not self.winfo_exists():
            return

        if psutil:
            try:
                cpu = f"{psutil.cpu_percent(interval=None):.0f}%"
                vm = psutil.virtual_memory()
                ram = f"{vm.percent:.0f}%"
            except Exception as e:
                logger.debug("psutil: %s", e)
                cpu, ram = "?", "?"
        else:
            cpu = ram = "install psutil"

        if config.get("stats_show_cpu"):
            self._lbl_cpu.configure(text=cpu)
        else:
            self._lbl_cpu.configure(text="off")

        if config.get("stats_show_ram"):
            self._lbl_ram.configure(text=ram)
        else:
            self._lbl_ram.configure(text="off")

        if config.get("stats_show_gpu"):
            self._lbl_gpu.configure(text=self._gpu_text())
        else:
            self._lbl_gpu.configure(text="off")
