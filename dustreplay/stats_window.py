"""Hardware overlay: only enabled metrics (CPU/RAM/GPU/FPS), bar graphs + FPS sparkline."""

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

# Layout + size by mode (compact = small footprint + a bit more see-through via alpha_mul).
_MODE_PRESETS: dict[str, dict] = {
    "compact": {
        "win_w": 196,
        "title_fs": 10,
        "label_w": 30,
        "name_fs": 9,
        "bar_h": 6,
        "val_fs": 9,
        "val_w": 36,
        "row_pady": 2,
        "hdr_h": 20,
        "pad_x": 6,
        "pad_top": 4,
        "pad_bottom": 8,
        "fps_val_fs": 15,
        "fps_canvas_h": 22,
        "spark_max": 32,
        "alpha_mul": 0.88,
        "row_slot": 30,
        "fps_slot": 50,
    },
    "normal": {
        "win_w": 234,
        "title_fs": 11,
        "label_w": 34,
        "name_fs": 10,
        "bar_h": 9,
        "val_fs": 10,
        "val_w": 42,
        "row_pady": 3,
        "hdr_h": 22,
        "pad_x": 8,
        "pad_top": 6,
        "pad_bottom": 8,
        "fps_val_fs": 18,
        "fps_canvas_h": 30,
        "spark_max": 48,
        "alpha_mul": 0.95,
        "row_slot": 36,
        "fps_slot": 62,
    },
    "advanced": {
        "win_w": 276,
        "title_fs": 12,
        "label_w": 40,
        "name_fs": 11,
        "bar_h": 12,
        "val_fs": 11,
        "val_w": 48,
        "row_pady": 4,
        "hdr_h": 24,
        "pad_x": 10,
        "pad_top": 6,
        "pad_bottom": 10,
        "fps_val_fs": 22,
        "fps_canvas_h": 38,
        "spark_max": 72,
        "alpha_mul": 1.0,
        "row_slot": 42,
        "fps_slot": 76,
    },
}


def _subprocess_flags():
    if sys.platform == "win32":
        try:
            return subprocess.CREATE_NO_WINDOW
        except Exception:
            pass
    return 0


def _query_nvidia_gpu_util() -> float | None:
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


def _norm_mode() -> str:
    v = (config.get("stats_overlay_mode") or "normal").lower()
    return v if v in _MODE_PRESETS else "normal"


def _visible_series() -> list[str]:
    out: list[str] = []
    if config.get("stats_show_cpu"):
        out.append("cpu")
    if config.get("stats_show_ram"):
        out.append("ram")
    if config.get("stats_show_gpu"):
        out.append("gpu")
    if config.get("stats_show_fps"):
        out.append("fps")
    return out


class StatsWindow(ctk.CTkToplevel):
    """Borderless corner overlay. Close from Home (Statistics) tap again. No title-bar X."""

    def __init__(self, master, recorder, app_ref):
        super().__init__(master)
        self.recorder = recorder
        self._app = app_ref
        self._tick_id = None
        self._gpu_cache_v: float | None = None
        self._gpu_cache_at = 0.0

        self._mode = _norm_mode()
        self._m = _MODE_PRESETS[self._mode]
        self._series = _visible_series()
        self._fps_hist: deque[int] = deque(maxlen=int(self._m["spark_max"]))

        self._W = int(self._m["win_w"])
        n_bar = sum(1 for k in self._series if k != "fps")
        has_fps = "fps" in self._series
        self._H = (
            int(self._m["pad_top"])
            + int(self._m["hdr_h"])
            + 4
            + n_bar * int(self._m["row_slot"])
            + (int(self._m["fps_slot"]) if has_fps else 0)
            + int(self._m["pad_bottom"])
        )

        self.overrideredirect(True)
        self.attributes("-topmost", True)
        try:
            base = float(config.get("stats_overlay_alpha") or 0.78)
            base = max(0.35, min(1.0, base))
            a = max(0.35, min(1.0, base * float(self._m["alpha_mul"])))
        except Exception:
            a = 0.75
        self.attributes("-alpha", a)

        self.configure(fg_color=_BG)
        self.resizable(False, False)
        self.minsize(self._W, self._H)
        self.maxsize(self._W, self._H)

        outer = ctk.CTkFrame(self, fg_color=_BG, corner_radius=0, border_width=0)
        outer.pack(fill="both", expand=True, padx=0, pady=0)

        px = int(self._m["pad_x"])
        hdr = ctk.CTkFrame(outer, fg_color=_BG, height=int(self._m["hdr_h"]))
        hdr.pack(fill="x", padx=px, pady=(int(self._m["pad_top"]), 2))
        hdr.pack_propagate(False)
        ctk.CTkLabel(
            hdr,
            text=i18n.t("stats.title"),
            font=ctk.CTkFont(size=int(self._m["title_fs"]), weight="bold"),
            text_color=_LBL,
            anchor="w",
        ).pack(side="left")

        self._body = ctk.CTkFrame(outer, fg_color=_BG)
        self._body.pack(fill="both", expand=True, padx=px, pady=(0, int(self._m["pad_bottom"])))
        self._body.grid_columnconfigure(0, weight=1)

        self._widgets: dict[str, object] = {}
        row = 0
        for key in self._series:
            if key == "fps":
                self._widgets["fps"] = self._build_fps_row(row)
            else:
                title = i18n.t(f"stats.{key}")
                self._widgets[key] = self._build_bar_row(row, title)
            row += 1

        self.protocol("WM_DELETE_WINDOW", self._close)
        self._apply_corner_geometry()
        self._schedule_tick()
        try:
            self.lift()
            self.attributes("-topmost", True)
        except Exception:
            pass

    def _build_bar_row(self, row: int, title: str):
        m = self._m
        row_fr = ctk.CTkFrame(self._body, fg_color=_ROW, corner_radius=4)
        row_fr.grid(row=row, column=0, sticky="ew", pady=int(m["row_pady"]))
        row_fr.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            row_fr,
            text=title,
            font=ctk.CTkFont(size=int(m["name_fs"]), weight="bold"),
            text_color=_LBL,
            width=int(m["label_w"]),
            anchor="w",
        ).grid(row=0, column=0, padx=(8, 4), pady=6)

        bar = ctk.CTkProgressBar(
            row_fr,
            height=int(m["bar_h"]),
            progress_color=_VAL,
            fg_color=_BAR_BG,
            corner_radius=3,
        )
        bar.grid(row=0, column=1, sticky="ew", padx=0, pady=6)
        bar.set(0)

        txt = ctk.CTkLabel(
            row_fr,
            text="--",
            font=ctk.CTkFont(size=int(m["val_fs"]), weight="bold"),
            text_color=_VAL,
            width=int(m["val_w"]),
            anchor="e",
        )
        txt.grid(row=0, column=2, padx=(4, 8), pady=6)
        return bar, txt

    def _build_fps_row(self, row: int):
        m = self._m
        fr = ctk.CTkFrame(self._body, fg_color=_ROW, corner_radius=4)
        fr.grid(row=row, column=0, sticky="ew", pady=int(m["row_pady"]))
        fr.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(
            fr,
            text=i18n.t("stats.fps"),
            font=ctk.CTkFont(size=int(m["name_fs"]), weight="bold"),
            text_color=_LBL,
            width=int(m["label_w"]),
            anchor="w",
        ).grid(row=0, column=0, rowspan=2, padx=(8, 4), pady=(8, 8), sticky="n")

        self._fps_val = ctk.CTkLabel(
            fr,
            text="--",
            font=ctk.CTkFont(size=int(m["fps_val_fs"]), weight="bold"),
            text_color=_VAL,
            anchor="w",
        )
        self._fps_val.grid(row=0, column=1, sticky="ew", padx=0, pady=(6, 0))

        ch = int(m["fps_canvas_h"])
        self._fps_canvas = tk.Canvas(
            fr,
            height=ch,
            bg=_ROW,
            highlightthickness=0,
            bd=0,
        )
        self._fps_canvas.grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=(0, 6))
        fr.bind("<Configure>", self._on_fps_canvas_configure)
        return fr

    def _on_fps_canvas_configure(self, event=None):
        try:
            self._fps_canvas.configure(width=max(self._fps_canvas.winfo_width(), 60))
        except Exception:
            pass

    def _gpu_util_cached(self) -> float | None:
        if "gpu" not in self._widgets:
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
        h = max(int(cv.winfo_height()), 16)
        cap = max(max(hist), int(config.get("fps") or 60) * 2, 30)
        n = len(hist)
        pts = []
        for i, v in enumerate(hist):
            x = 2 + (i / max(n - 1, 1)) * (w - 4)
            y = h - 4 - (min(v, cap) / cap) * (h - 8)
            pts.append((x, y))
        lw = 2 if self._mode != "compact" else 1
        for i in range(1, len(pts)):
            cv.create_line(
                pts[i - 1][0],
                pts[i - 1][1],
                pts[i][0],
                pts[i][1],
                fill=_VAL,
                width=lw,
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

        wcpu = self._widgets.get("cpu")
        if wcpu:
            bar, txt = wcpu  # type: ignore[misc]
            bar.set(max(0.0, min(1.0, cpu_p / 100.0)))
            txt.configure(text=f"{cpu_p:.0f}%")

        wram = self._widgets.get("ram")
        if wram:
            bar, txt = wram  # type: ignore[misc]
            bar.set(max(0.0, min(1.0, ram_p / 100.0)))
            txt.configure(text=f"{ram_p:.0f}%")

        wgpu = self._widgets.get("gpu")
        if wgpu:
            bar, txt = wgpu  # type: ignore[misc]
            gu = self._gpu_util_cached()
            if gu is not None:
                bar.set(max(0.0, min(1.0, gu / 100.0)))
                txt.configure(text=f"{int(round(gu))}%")
            else:
                bar.set(0)
                txt.configure(text="--")

        if "fps" in self._widgets:
            try:
                n = int(self.recorder.estimate_capture_fps())
            except Exception:
                n = 0
            self._fps_val.configure(text=str(max(0, n)))
            self._fps_hist.append(n)
            self._draw_fps_sparkline()
