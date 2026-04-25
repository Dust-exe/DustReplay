"""Frameless compact hardware overlay: CPU / RAM / GPU / FPS, corner snap only."""

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
_LBL = "#ffffff"
_VAL = "#aa77ff"
_CORNERS = ("tl", "tr", "bl", "br")


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
    """Small borderless overlay; position = screen corner only (no drag)."""

    _W = 132
    _H = 128

    def __init__(self, master, recorder, app_ref):
        super().__init__(master)
        self.recorder = recorder
        self._app = app_ref
        self._tick_id = None
        self._gpu_cache = ""
        self._gpu_cache_at = 0.0
        self._corner_btns: dict[str, ctk.CTkButton] = {}

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

        hdr = ctk.CTkFrame(outer, fg_color="transparent", height=20)
        hdr.pack(fill="x", padx=6, pady=(4, 0))
        hdr.pack_propagate(False)

        self._hdr_title = ctk.CTkLabel(
            hdr,
            text="Hardware",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=_LBL,
            anchor="w",
        )
        self._hdr_title.pack(side="left")

        ctk.CTkButton(
            hdr,
            text="\u2715",
            width=18,
            height=18,
            font=ctk.CTkFont(size=11),
            fg_color="#15151c",
            hover_color="#252530",
            corner_radius=3,
            text_color="#cccccc",
            command=self._close,
        ).pack(side="right")

        cr = ctk.CTkFrame(outer, fg_color="transparent", height=20)
        cr.pack(fill="x", padx=4, pady=(2, 2))
        cr.pack_propagate(False)
        inn = ctk.CTkFrame(cr, fg_color="transparent")
        inn.place(relx=0.5, rely=0.5, anchor="center")

        for code, txt in zip(_CORNERS, ("TL", "TR", "BL", "BR")):
            b = ctk.CTkButton(
                inn,
                text=txt,
                width=28,
                height=18,
                font=ctk.CTkFont(size=9, weight="bold"),
                fg_color="#12121a",
                hover_color="#1e1e28",
                corner_radius=3,
                text_color="#888899",
                border_width=0,
                command=lambda c=code: self._set_corner(c),
            )
            b.pack(side="left", padx=1)
            self._corner_btns[code] = b

        self._body = ctk.CTkFrame(outer, fg_color="transparent")
        self._body.pack(fill="both", expand=True, padx=6, pady=(0, 4))

        self._lbl_cpu = self._metric_row(0, "CPU")
        self._lbl_ram = self._metric_row(1, "RAM")
        self._lbl_gpu = self._metric_row(2, "GPU")
        self._lbl_fps = self._metric_row(3, "FPS")

        self.protocol("WM_DELETE_WINDOW", self._close)
        self._sync_corner_buttons()
        self._apply_corner_geometry()
        self._schedule_tick()

    def _metric_row(self, row: int, name: str):
        fr = ctk.CTkFrame(self._body, fg_color="transparent")
        fr.grid(row=row, column=0, sticky="ew", pady=1)
        self._body.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            fr,
            text=name,
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=_LBL,
            width=34,
            anchor="w",
        ).pack(side="left")
        val = ctk.CTkLabel(
            fr,
            text="--",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=_VAL,
            anchor="e",
        )
        val.pack(side="right", fill="x", expand=True)
        return val

    def _set_corner(self, code: str):
        if code not in _CORNERS:
            return
        config.set("stats_overlay_corner", code)
        try:
            config.save()
        except Exception as e:
            logger.debug("stats overlay corner save: %s", e)
        self._apply_corner_geometry()
        self._sync_corner_buttons()

    def _sync_corner_buttons(self):
        cur = (config.get("stats_overlay_corner") or "br").lower()
        if cur not in _CORNERS:
            cur = "br"
        for c, btn in self._corner_btns.items():
            on = c == cur
            btn.configure(
                fg_color="#1c1c26" if on else "#12121a",
                text_color=_LBL if on else "#888899",
                border_width=1 if on else 0,
                border_color="#3a3a48" if on else "#12121a",
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
            cpu, ram = "--", "--"

        if config.get("stats_show_cpu"):
            self._lbl_cpu.configure(text=cpu)
        else:
            self._lbl_cpu.configure(text="--")

        if config.get("stats_show_ram"):
            self._lbl_ram.configure(text=ram)
        else:
            self._lbl_ram.configure(text="--")

        if config.get("stats_show_gpu"):
            self._lbl_gpu.configure(text=self._gpu_text())
        else:
            self._lbl_gpu.configure(text="--")

        if config.get("stats_show_fps"):
            try:
                n = self.recorder.estimate_capture_fps()
                self._lbl_fps.configure(text=str(n))
            except Exception:
                self._lbl_fps.configure(text="--")
        else:
            self._lbl_fps.configure(text="--")
