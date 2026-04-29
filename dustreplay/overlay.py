import tkinter as tk

import config
import theme

_W, _H = 56, 22


class RecordingOverlay:
    def __init__(self, master):
        self._master = master
        self._win = None
        self._canvas = None
        self._dx = self._dy = 0
        if config.get("overlay_enabled"):
            self._build()

    def _build(self):
        self._win = tk.Toplevel(self._master)
        self._win.overrideredirect(True)
        self._win.attributes("-topmost", True)
        self._win.attributes("-alpha", 0.78)
        self._win.configure(bg="#000001")
        try:
            self._win.wm_attributes("-transparentcolor", "#000001")
        except Exception:
            pass
        self._win.resizable(False, False)

        c = tk.Canvas(self._win, width=_W, height=_H, bg="#000001", highlightthickness=0)
        c.pack()
        self._canvas = c

        r = _H // 2
        c.create_oval(
            0, 0, _H, _H, fill=theme.ACCENT_DEEP, outline=theme.SEPARATOR, width=1
        )
        c.create_oval(
            _W - _H, 0, _W, _H, fill=theme.ACCENT_DEEP, outline=theme.SEPARATOR, width=1
        )
        c.create_rectangle(r, 0, _W - r, _H, fill=theme.ACCENT_DEEP, outline="")
        c.create_rectangle(r, 1, _W - r, _H - 1, fill=theme.ACCENT_DEEP, outline="")

        c.create_oval(6, 7, 15, 16, fill=theme.ACCENT, outline="")

        c.create_text(
            _W // 2 + 5,
            _H // 2,
            text="REC",
            fill=theme.TEXT_SOFT,
            font=("Arial", 8, "bold"),
            anchor="center",
        )

        c.bind("<Button-1>", self._drag_start)
        c.bind("<B1-Motion>", self._drag_motion)
        c.bind("<ButtonRelease-1>", self._drag_end)

        self._apply_pos()
        self._win.withdraw()

    def _apply_pos(self):
        if not self._win:
            return
        x = config.get("overlay_x")
        y = config.get("overlay_y")
        sw = self._win.winfo_screenwidth()
        sh = self._win.winfo_screenheight()
        x = max(0, min(x, sw - _W))
        y = max(0, min(y, sh - _H))
        self._win.geometry(f"{_W}x{_H}+{x}+{y}")

    def _drag_start(self, e):
        self._dx = e.x_root - self._win.winfo_x()
        self._dy = e.y_root - self._win.winfo_y()

    def _drag_motion(self, e):
        if self._win:
            self._win.geometry(f"+{e.x_root - self._dx}+{e.y_root - self._dy}")

    def _drag_end(self, e):
        if not self._win:
            return
        config.set("overlay_x", self._win.winfo_x())
        config.set("overlay_y", self._win.winfo_y())
        config.save()

    def show(self):
        if self._win:
            try:
                self._win.deiconify()
                self._win.lift()
            except Exception:
                pass

    def hide(self):
        if self._win:
            try:
                self._win.withdraw()
            except Exception:
                pass

    def toggle_enabled(self, enabled):
        config.set("overlay_enabled", enabled)
        config.save()
        if enabled and not self._win:
            self._build()
        elif not enabled:
            self.hide()

    def destroy(self):
        if self._win:
            try:
                self._win.destroy()
            except Exception:
                pass
            self._win = None
