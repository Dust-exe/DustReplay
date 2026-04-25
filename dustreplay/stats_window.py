"""Frameless hardware overlay: CPU / RAM / GPU as bar graphs, FPS + sparkline."""

from __future__ import annotations

import logging
import subprocess
import sys
import time
import tkinter as tk
from collections import deque

import customtkinter as ctk

import config
import i18n

logger = logging.getLogger(__name__)

try:
    import psutil
except ImportError:
    psutil = None

_BG = "#0a0612"
_ROW = "#120818"
_LBL = "#ffffff"
_VAL = "#aa77ff"
_BAR_BG = "#2a1a38"
_CORNERS = ("tl", "tr", "bl", "br")


def _subprocess_flags():
    if sys.platform == "win32":
        try:
            return subprocess.CREATE_NO_WINDOW
        except Exception:
            pass
    return 0


def _query_nvidia_gpu_util() -> float | None:
    """GPU utilization 0..100, or None if unavailable."""
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
        return float(line)
    except FileNotFoundError:
        return None
    except Exception as e:
        logger.debug("nvidia-smi: %s", e)
        return None


class StatsWindow(ctk.CTkToplevel):
    """Small borderless overlay; corner snap. Close from Home (Statistics) again — no X button."""

    _W = 256
    _H = 232

    def __init__(self, master, recorder, app_ref):
        super().__init__(master)
        self.recorder = recorder
        self._app = app_ref
        self._tick_id = None
        self._gpu_cache_v: float | None = None
        self._gpu_cache_at = 0.0
        self._fps_hist: deque[int] = deque(maxlen=48)

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

        outer = ctk.CTkFrame(self, fg_color=_BG, corner_radius=0, border_width=0)
        outer.pack(fill="both", expand=True, padx=0, pady=0)

        hdr = ctk.CTkFrame(outer, fg_color=_BG, height=22)
        hdr.pack(fill="x", padx=8, pady=(6, 2))
        hdr.pack_propagate(False)
        ctk.CTkLabel(
            hdr,
            text=i18n.t("stats.title"),
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=_LBL,
            anchor="w",
        ).pack(side="left")

        self._body = ctk.CTkFrame(outer, fg_color=_BG)
        self._body.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self._body.grid_columnconfigure(0, weight=1)

        self._bar_cpu, self._txt_cpu = self._bar_row(0, i18n.t("stats.cpu"))
        self._bar_ram, self._txt_ram = self._bar_row(1, i18n.t("stats.ram"))
        self._bar_gpu, self._txt_gpu = self._bar_row(2, i18n.t("stats.gpu"))
        self._build_fps_row(3)

        self.protocol("WM_DELETE_WINDOW", self._close)
        self._apply_corner_geometry()
        self._schedule_tick()
        try:
            self.lift()
            self.attributes("-topmost", True)
        except Exception:
            pass

    def _bar_row(self, row: int, title: str):
        row_fr = ctk.CTkFrame(self._body, fg_color=_ROW, corner_radius=4)
        row_fr.grid(row=row, column=0, sticky="ew", pady=3)
        row_fr.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            row_fr,
            text=title,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=_LBL,
            width=36,
            anchor="w",
        ).grid(row=0, column=0, padx=(8, 4), pady=6)

        bar = ctk.CTkProgressBar(
            row_fr,
            height=10,
            progress_color=_VAL,
            fg_color=_BAR_BG,
            corner_radius=3,
        )
        bar.grid(row=0, column=1, sticky="ew", padx=0, pady=6)
        bar.set(0)

        txt = ctk.CTkLabel(
            row_fr,
            text="--",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=_VAL,
            width=44,
            anchor="e",
        )
        txt.grid(row=0, column=2, padx=(4, 8), pady=6)
        return bar, txt

    def _build_fps_row(self, row: int):
        fr = ctk.CTkFrame(self._body, fg_color=_ROW, corner_radius=4)
        fr.grid(row=row, column=0, sticky="ew", pady=3)
        fr.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            fr,
            text=i18n.t("stats.fps"),
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=_LBL,
            width=36,
            anchor="w",
        ).grid(row=0, column=0, rowspan=2, padx=(8, 4), pady=(8, 8), sticky="n")

        self._fps_val = ctk.CTkLabel(
            fr,
            text="--",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=_VAL,
            anchor="w",
        )
        self._fps_val.grid(row=0, column=1, sticky="ew", padx=0, pady=(6, 0))

        self._fps_canvas = tk.Canvas(
            fr,
            height=34,
            bg=_ROW,
            highlightthickness=0,
            bd=0,
        )
        self._fps_canvas.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(0, 6))
        fr.bind("<Configure>", self._on_fps_canvas_configure)

    def _on_fps_canvas_configure(self, event=None):
        try:
            self._fps_canvas.configure(width=max(self._fps_canvas.winfo_width(), 80))
        except Exception:
            pass

    def _gpu_util_cached(self) -> float | None:
        if not config.get("stats_show_gpu"):
            return None
        now = time.time()
        if now - self._gpu_cache_at < 1.5 and self._gpu_cache_v is not None:
            return self._gpu_cache_v
        self._gpu_cache_at = now
        self._gpu_cache_v = _query_nvidia_gpu_util()
        return self._gpu_cache_v

    def _draw_fps_sparkline(self):
        cv = self._fps_canvas
        try:
            cv.delete("all")
        except Exception:
            return
        hist = list(self._fps_hist)
        if len(hist) < 2:
            return
        w = max(int(cv.winfo_width()), 40)
        h = max(int(cv.winfo_height()), 20)
        cap = max(max(hist), int(config.get("fps") or 60) * 2, 30)
        pts = []
        n = len(hist)
        for i, v in enumerate(hist):
            x = 2 + (i / max(n - 1, 1)) * (w - 4)
            y = h - 4 - (min(v, cap) / cap) * (h - 8)
            pts.append((x, y))
        for i in range(1, len(pts)):
            cv.create_line(
                pts[i - 1][0],
                pts[i - 1][1],
                pts[i][0],
                pts[i][1],
                fill=_VAL,
                width=2,
            )

    def _apply_corner_geometry(self):
        try:
            self.update_idletasks()
            sw = self.winfo_screenwidth()
            sh = self.winfo_screenheight()
            w, h = self._W, self._H
            m = 8
            tb = 40
            code = (config.get("stats_overlay_corner") or "br").lower()
            if code not in _CORNERS:
                code = "br"
            if code == "tl":
                gx, gy = m, m
            elif code == "tr":
                gx, gy = sw - w - m, m
            elif code == "bl":
                gx, gy = m, sh - h - m - tb
            else:
                gx, gy = sw - w - m, sh - h - m - tb
            gx = max(0, min(gx, max(0, sw - w)))
            gy = max(0, min(gy, max(0, sh - h)))
            self.geometry(f"{w}x{h}+{gx}+{gy}")
        except Exception:
            self.geometry(f"{self._W}x{self._H}+20+20")

    def _close(self):
        self.destroy()

    def _schedule_tick(self):
        try:
            self._refresh()
        except Exception as e:
            logger.debug("stats refresh: %s", e)
        self._tick_id = self.after(500, self._schedule_tick)

    def destroy(self):
        if self._tick_id:
            try:
                self.after_cancel(self._tick_id)
            except Exception:
                pass
            self._tick_id = None
        try:
            app = getattr(self, "_app", None)
            if app is not None and getattr(app, "_stats_win", None) is self:
                app._stats_win = None
        except Exception:
            pass
        super().destroy()

    def _refresh(self):
        if not self.winfo_exists():
            return

        if psutil:
            try:
                cpu_p = float(psutil.cpu_percent(interval=None))
                ram_p = float(psutil.virtual_memory().percent)
            except Exception as e:
                logger.debug("psutil: %s", e)
                cpu_p, ram_p = 0.0, 0.0
        else:
            cpu_p, ram_p = 0.0, 0.0

        if config.get("stats_show_cpu"):
            self._bar_cpu.set(max(0.0, min(1.0, cpu_p / 100.0)))
            self._txt_cpu.configure(text=f"{cpu_p:.0f}%")
        else:
            self._bar_cpu.set(0)
            self._txt_cpu.configure(text="--")

        if config.get("stats_show_ram"):
            self._bar_ram.set(max(0.0, min(1.0, ram_p / 100.0)))
            self._txt_ram.configure(text=f"{ram_p:.0f}%")
        else:
            self._bar_ram.set(0)
            self._txt_ram.configure(text="--")

        if config.get("stats_show_gpu"):
            gu = self._gpu_util_cached()
            if gu is not None:
                self._bar_gpu.set(max(0.0, min(1.0, gu / 100.0)))
                self._txt_gpu.configure(text=f"{int(round(gu))}%")
            else:
                self._bar_gpu.set(0)
                self._txt_gpu.configure(text="--")
        else:
            self._bar_gpu.set(0)
            self._txt_gpu.configure(text="--")

        if config.get("stats_show_fps"):
            try:
                n = int(self.recorder.estimate_capture_fps())
            except Exception:
                n = 0
            self._fps_val.configure(text=str(max(0, n)))
            self._fps_hist.append(n)
            self._draw_fps_sparkline()
        else:
            self._fps_val.configure(text="--")
            self._fps_hist.clear()
            try:
                self._fps_canvas.delete("all")
            except Exception:
                pass
