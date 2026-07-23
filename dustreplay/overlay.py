"""Minimal on-screen recording dot (corner + click-through on Windows)."""

import sys
import tkinter as tk

import config
import theme

# Tiny square window; only the inner circle is visible (chroma outside).
_WIN = 14
_MARGIN = 10
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
            width=_WIN,
            height=_WIN,
            bg=_CHROMA,
            highlightthickness=0,
        )
        c.pack()
        self._canvas = c
        cx, cy, r = _WIN // 2, _WIN // 2, 4
        c.create_oval(
            cx - r,
            cy - r,
            cx + r,
            cy + r,
            fill=theme.ACCENT,
            outline=theme.ACCENT_DEEP,
            width=1,
        )

        self._apply_pos()
        self._win.withdraw()
        self._schedule_clickthrough()
        self._pulse()

    def _pulse(self):
        if not self._win:
            return
        if self._is_showing:
            import time
            import math
            val = (math.sin(time.time() * math.pi) + 1) / 2
            try:
                self._win.attributes("-alpha", 0.6 + val * 0.4)
            except Exception:
                pass
        else:
            try:
                self._win.attributes("-alpha", 1.0)
            except Exception:
                pass
        self._win.after(50, self._pulse)

    def _apply_pos(self):
        if not self._win:
            return
        corner = (config.get("overlay_corner") or "tr").lower()
        if corner not in ("tl", "tr", "bl", "br"):
            corner = "tr"
        sw = self._win.winfo_screenwidth()
        sh = self._win.winfo_screenheight()
        w, h = _WIN, _WIN
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
