"""Sleek ShadowPlay-style on-screen recording HUD indicator (corner + click-through on Windows)."""

import math
import sys
import time
import tkinter as tk

import config
import theme

_WIN_W = 48
_WIN_H = 22
_MARGIN = 14
_CHROMA = "#010101"


def _set_clickthrough_win32(hwnd: int) -> None:
    if sys.platform != "win32" or not hwnd:
        return
    try:
        import ctypes

        GWL_EXSTYLE = -20
        WS_EX_LAYERED = 0x00080000
        WS_EX_TRANSPARENT = 0x00000020
        user32 = ctypes.windll.user32
        get_long = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
        set_long = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
        ex = int(get_long(hwnd, GWL_EXSTYLE))
        set_long(hwnd, GWL_EXSTYLE, ex | WS_EX_LAYERED | WS_EX_TRANSPARENT)
    except Exception:
        pass


class RecordingOverlay:
    def __init__(self, master):
        self._master = master
        self._win = None
        self._canvas = None
        self._dot = None
        self._glow = None
        self._is_showing = False
        if config.get("overlay_enabled"):
            self._build()

    def _schedule_clickthrough(self):
        if not self._win or sys.platform != "win32":
            return

        def _go():
            try:
                hwnd = int(self._win.winfo_id())
                _set_clickthrough_win32(hwnd)
            except Exception:
                pass

        try:
            self._win.after(80, _go)
        except Exception:
            pass

    def _create_round_rect(self, canvas, x1, y1, x2, y2, r, **kwargs):
        points = [
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1,
        ]
        return canvas.create_polygon(points, smooth=True, **kwargs)

    def _build(self):
        self._win = tk.Toplevel(self._master)
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", True)
        self._win.attributes("-alpha", 1.0)
        self._win.configure(bg=_CHROMA)
        try:
            self._win.wm_attributes("-transparentcolor", _CHROMA)
        except Exception:
            pass
        self._win.resizable(False, False)

        c = tk.Canvas(
            self._win,
            width=_WIN_W,
            height=_WIN_H,
            bg=_CHROMA,
            highlightthickness=0,
        )
        c.pack()
        self._canvas = c

        # Sleek dark translucent pill backdrop
        self._create_round_rect(
            c, 1, 1, _WIN_W - 1, _WIN_H - 1, r=8,
            fill="#0f0f18", outline="#26253a", width=1
        )

        # Outer soft glow ring for dot
        cx, cy = 11, 11
        self._glow = c.create_oval(
            cx - 5, cy - 5, cx + 5, cy + 5,
            fill="#551122", outline="", state="normal"
        )

        # Inner bright crimson recording dot
        self._dot = c.create_oval(
            cx - 3.5, cy - 3.5, cx + 3.5, cy + 3.5,
            fill="#ff2d55", outline="#ff6b8b", width=1
        )

        # REC label text
        c.create_text(
            30, 11,
            text="REC",
            fill="#e2e2ec",
            font=("Segoe UI", 7, "bold")
        )

        self._apply_pos()
        self._win.withdraw()
        self._schedule_clickthrough()
        self._pulse()

    def _pulse(self):
        if not self._win:
            return
        if self._is_showing:
            val = (math.sin(time.time() * 3.5) + 1) / 2
            try:
                # Breathing opacity for the window
                self._win.attributes("-alpha", 0.7 + val * 0.3)
                # Pulse glow size/visibility
                if self._canvas and self._glow:
                    dot_color = "#ff2d55" if val > 0.3 else "#cc1133"
                    self._canvas.itemconfig(self._dot, fill=dot_color)
            except Exception:
                pass
        else:
            try:
                self._win.attributes("-alpha", 1.0)
            except Exception:
                pass
        self._win.after(40, self._pulse)

    def _apply_pos(self):
        if not self._win:
            return
        corner = (config.get("overlay_corner") or "tr").lower()
        if corner not in ("tl", "tr", "bl", "br"):
            corner = "tr"
        sw = self._win.winfo_screenwidth()
        sh = self._win.winfo_screenheight()
        w, h = _WIN_W, _WIN_H
        if corner == "tl":
            x, y = _MARGIN, _MARGIN
        elif corner == "tr":
            x, y = sw - w - _MARGIN, _MARGIN
        elif corner == "bl":
            x, y = _MARGIN, sh - h - _MARGIN
        else:
            x, y = sw - w - _MARGIN, sh - h - _MARGIN
        self._win.geometry(f"{w}x{h}+{x}+{y}")

    def show(self):
        if self._win:
            try:
                self._is_showing = True
                self._apply_pos()
                self._win.deiconify()
                self._win.lift()
                self._schedule_clickthrough()
            except Exception:
                pass

    def hide(self):
        if self._win:
            try:
                self._is_showing = False
                self._win.withdraw()
            except Exception:
                pass

    def toggle_enabled(self, enabled: bool):
        if enabled:
            if not self._win:
                self._build()
            self.show()
        else:
            self.hide()

    def destroy(self):
        if self._win:
            try:
                self._win.destroy()
            except Exception:
                pass
            self._win = None
            self._canvas = None
