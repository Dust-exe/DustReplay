import logging
import os
import threading
from datetime import datetime

import customtkinter as ctk
import pystray
from PIL import Image, ImageDraw

import branding_paths
import config
import i18n
import startup
import theme
from overlay import RecordingOverlay
from page_home import HomePage
import saver as saver_mod
from stats_window import StatsWindow

logger = logging.getLogger(__name__)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

_P = theme.P
_PH = theme.PH
_BG = theme.BG
_CBG = theme.CBG
_SBG = theme.SBG
_PANEL_W = 340


def _hide_from_taskbar(win):
    """Side panel is a tray overlay — do not add a second taskbar button on Windows."""
    try:
        import ctypes

        win.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(win.winfo_id())
        if not hwnd:
            hwnd = win.winfo_id()
        gwl_exstyle = -20
        ws_toolwindow = 0x00000080
        ws_appwindow = 0x00040000
        style = ctypes.windll.user32.GetWindowLongW(hwnd, gwl_exstyle)
        style = (style | ws_toolwindow) & ~ws_appwindow
        ctypes.windll.user32.SetWindowLongW(hwnd, gwl_exstyle, style)
        ctypes.windll.user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, 0x0027)
    except Exception as e:
        logger.debug("hide_from_taskbar: %s", e)


def _ti(rec):
    sz = 64
    bg = (20, 16, 24, 255)
    img = Image.new("RGBA", (sz, sz), bg)
    path = branding_paths.logo_png_path()
    if os.path.isfile(path):
        src = Image.open(path).convert("RGBA")
        margin = 4
        inner = sz - 2 * margin
        src.thumbnail((inner, inner), Image.Resampling.LANCZOS)
        x = margin + (inner - src.width) // 2
        y = margin + (inner - src.height) // 2
        img.paste(src, (x, y), src)
    else:
        d0 = ImageDraw.Draw(img)
        d0.ellipse([2, 2, sz - 2, sz - 2], fill=(49, 10, 93, 230))
    d = ImageDraw.Draw(img)
    if rec:
        d.ellipse([sz - 20, sz - 20, sz - 4, sz - 4], fill=(196, 68, 68, 255))
        d.ellipse([sz - 17, sz - 17, sz - 7, sz - 7], fill=(255, 140, 130, 255))
    else:
        d.ellipse([sz - 18, sz - 18, sz - 6, sz - 6], fill=(110, 100, 128, 220))
    return img


class AppWindow(ctk.CTk):
    def __init__(self, recorder, watchdog):
        super().__init__()
        import time as _time

        self._start_time = _time.time()
        self.recorder = recorder
        self.watchdog = watchdog
        self._recording = True
        self._tray_icon = None
        self.overlay = None
        self._panel_visible = False
        self._panel = None
        self._panel_backdrop = None
        self._stats_win = None
        self._last_manual = None
        self._resume_buffer_after_manual = True
        self.pages = {}
        self.rec_dot = None
        self._badge = None
        self._nb = {}
        self._hk_save = None
        self._hk_toggle = None
        self._hk_panel = None
        self.protocol("WM_DELETE_WINDOW", lambda: None)
        self.withdraw()
        self.update()
        self._build_panel()
        self._btray()
        self.overlay = RecordingOverlay(self)
        self._tick()

    def register_global_hotkeys(self):
        """Register or refresh global hotkeys (call after settings change)."""
        import keyboard as kb

        self._clear_global_hotkeys()
        try:
            self._hk_save = kb.add_hotkey(
                config.get("hotkey_save"),
                lambda: self.after(0, self._do_save_impl),
                suppress=False,
            )
            self._hk_toggle = kb.add_hotkey(
                config.get("hotkey_toggle"),
                lambda: self.after(0, self._do_toggle_impl),
                suppress=False,
            )
            self._hk_panel = kb.add_hotkey(
                config.get("panel_hotkey"),
                lambda: self.after(0, self._toggle_panel_main),
                suppress=False,
            )
            logger.info("Global hotkeys registered.")
        except Exception as e:
            logger.error("Hotkey registration failed (try Run as administrator): %s", e)

    def _clear_global_hotkeys(self):
        import keyboard as kb

        for attr in ("_hk_save", "_hk_toggle", "_hk_panel"):
            h = getattr(self, attr, None)
            if h is not None:
                try:
                    kb.remove_hotkey(h)
                except Exception:
                    pass
                setattr(self, attr, None)

    def _build_panel(self):
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        p = ctk.CTkToplevel(self)
        p.withdraw()
        p.overrideredirect(True)
        p.attributes("-topmost", True)
        try:
            p.transient(self)
        except Exception:
            pass
        try:
            p.wm_attributes("-toolwindow", True)
        except Exception:
            pass
        try:
            p.wm_attributes("-skip_taskbar", True)
        except Exception:
            pass
        p.configure(fg_color=_BG)
        _init_x = 0 if config.get("panel_side") == "left" else sw - _PANEL_W
        p.geometry(f"{_PANEL_W}x{sh}+{_init_x}+0")
        p.resizable(False, False)
        self._panel = p

        hdr = ctk.CTkFrame(p, fg_color=theme.HEADER_BG, corner_radius=0, height=56)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        self._hdr_logo_img = None
        try:
            lp = branding_paths.logo_png_path()
            if os.path.isfile(lp):
                pil = Image.open(lp).convert("RGBA").resize(
                    (34, 34), Image.Resampling.LANCZOS
                )
                self._hdr_logo_img = ctk.CTkImage(
                    light_image=pil, dark_image=pil, size=(34, 34)
                )
                ctk.CTkLabel(hdr, image=self._hdr_logo_img, text="").pack(
                    side="left", padx=(12, 6), pady=10
                )
        except Exception:
            pass
        ctk.CTkLabel(
            hdr,
            text=config.APP_DISPLAY,
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=theme.TEXT,
        ).pack(side="left", padx=(0, 0), pady=14)
        self._badge = ctk.CTkLabel(
            hdr,
            text="LIVE",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="white",
            fg_color=theme.RED,
            corner_radius=5,
            width=44,
            height=18,
        )
        self._badge.pack(side="left", padx=4)
        ctk.CTkButton(
            hdr,
            text="\u2715",
            width=28,
            height=28,
            fg_color=theme.BTN_DARK,
            hover_color=theme.BTN_DARK_HOVER,
            corner_radius=6,
            font=ctk.CTkFont(size=13),
            command=self.toggle_panel,
        ).pack(side="right", padx=8)
        self.rec_dot = ctk.CTkLabel(
            hdr, text="\u23fa", font=ctk.CTkFont(size=11), text_color=theme.RED
        )
        self.rec_dot.pack(side="right", padx=2)
        ctk.CTkFrame(p, height=1, fg_color=theme.HEADER_LINE).pack(fill="x")

        self.content = ctk.CTkFrame(p, corner_radius=0, fg_color=_CBG)
        self.content.pack(fill="both", expand=True)
        self.pages = {
            "home": HomePage(self.content, app=self),
        }
        self.pages["home"].place(relx=0, rely=0, relwidth=1, relheight=1)

        # Simple dock: single button opens the main wide window
        self._dock_outer = ctk.CTkFrame(p, fg_color=theme.DOCK_BG, corner_radius=0)
        self._dock_outer.pack(side="bottom", fill="x")
        self._open_app_btn = ctk.CTkButton(
            self._dock_outer,
            text=i18n.t("nav.open_app"),
            height=50,
            fg_color=theme.DOCK_HANDLE,
            hover_color=theme.BTN_DARK,
            border_width=1,
            border_color=theme.ACCENT,
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=14,
            command=self.toggle_main_window,
        )
        self._open_app_btn.pack(fill="x", padx=10, pady=8)

        from version import __version__
        ctk.CTkLabel(
            self._dock_outer,
            text=f"v{__version__}",
            font=ctk.CTkFont(size=10),
            text_color=theme.VERSION_MUTED,
            fg_color=theme.DOCK_BG,
        ).pack(pady=(0, 6))

        self._nb = {}
        self._main_window = None
        self.refresh_ui_language()

    def toggle_main_window(self):
        if self._main_window is None or not self._main_window.winfo_exists():
            from main_window import MainWindow
            self._main_window = MainWindow(self)
        self.after(0, self._main_window.toggle)

    def sp(self, key):
        """Open main window on gallery / recordings / settings (from Alt+C panel)."""
        if self._main_window is None or not self._main_window.winfo_exists():
            from main_window import MainWindow
            self._main_window = MainWindow(self)
        mw = self._main_window
        page = key
        if page == "recordings":
            page = "recordings"
        elif page == "settings":
            page = "settings"
        elif page in ("gallery", "home"):
            page = "gallery"
        else:
            page = "gallery"

        def _open():
            if not mw.winfo_viewable():
                mw.deiconify()
                mw.lift()
                mw.focus_force()
            mw.show_page(page)

        self.after(0, _open)

    def _panel_x(self):
        sw = self.winfo_screenwidth()
        if config.get("panel_side") == "left":
            return 0
        return sw - _PANEL_W

    def _destroy_panel_backdrop(self):
        if self._panel_backdrop:
            try:
                self._panel_backdrop.destroy()
            except Exception:
                pass
            self._panel_backdrop = None

    def _close_panel_from_outside(self, event=None):
        if not self._panel_visible:
            return
        self.after(1, self._hide_panel)

    def _hide_panel(self):
        self._destroy_panel_backdrop()
        if self._panel:
            try:
                self._panel.attributes("-alpha", 1.0)
            except Exception:
                pass
            self._panel.withdraw()
        self._panel_visible = False

    def close_panel(self):
        self._hide_panel()

    def toggle_panel(self, event=None):
        """Always run panel show/hide on the Tk main thread (hotkeys call from a worker thread)."""
        self.after(0, self._toggle_panel_main)

    def _toggle_panel_main(self):
        if not self._panel:
            return
        if self._panel_visible:
            self._hide_panel()
            return
        import tkinter as tk

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        self._destroy_panel_backdrop()
        bd = tk.Toplevel(self)
        bd.overrideredirect(True)
        bd.configure(bg=theme.BACKDROP)
        bd.attributes("-alpha", 0.14)
        bd.attributes("-topmost", True)
        bd.bind("<Button-1>", self._close_panel_from_outside)
        self._panel_backdrop = bd

        x = self._panel_x()
        if config.get("panel_side") == "left":
            bd_w, bd_x = sw - _PANEL_W, _PANEL_W
        else:
            bd_w, bd_x = sw - _PANEL_W, 0
        bd.geometry(f"{bd_w}x{sh}+{bd_x}+0")

        self._panel.geometry(f"{_PANEL_W}x{sh}+{x}+0")
        self._panel.update_idletasks()
        self._panel.deiconify()
        _hide_from_taskbar(self._panel)
        _hide_from_taskbar(bd)
        try:
            self._panel.attributes("-alpha", 1.0)
        except Exception:
            pass
        self._panel.attributes("-topmost", True)
        self._panel.lift()
        try:
            bd.lower(self._panel)
        except Exception:
            bd.attributes("-topmost", False)
        self._panel.focus_force()
        self._panel_visible = True

    def _btray(self):
        ph = str(config.get("panel_hotkey")).upper()
        menu = pystray.Menu(
            pystray.MenuItem(
                "Open DustReplay",
                lambda i, it: self.after(0, self.toggle_main_window),
                default=True,
            ),
            pystray.MenuItem(
                "Show / hide panel",
                lambda i, it: self.after(0, self.toggle_panel),
            ),
            pystray.MenuItem("Save replay", lambda i, it: self.after(0, self.do_save)),
            pystray.MenuItem(
                "Stop / start capture", lambda i, it: self.after(0, self.do_toggle)
            ),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Quit", lambda i, it: self.after(0, self._quit)),
        )
        try:
            self._tray_icon = pystray.Icon(
                config.APP_DISPLAY,
                _ti(True),
                f"{config.APP_DISPLAY}  |  {ph}: panel",
                menu,
            )
            threading.Thread(target=self._tray_icon.run, daemon=True).start()
        except Exception as e:
            logger.error("Tray error: %s", e)

    def _quit(self):
        self._clear_global_hotkeys()
        self._hide_panel()
        try:
            if self._stats_win and self._stats_win.winfo_exists():
                self._stats_win.destroy()
        except Exception:
            pass
        self._stats_win = None
        if self.watchdog:
            self.watchdog.stop()
        self.recorder.stop_manual_recording()
        self.recorder.stop()
        if self.overlay:
            self.overlay.destroy()
        if self._tray_icon:
            self._tray_icon.stop()
        self.destroy()

    def _tick(self):
        try:
            self.recorder.cleanup_dead_manual()
            ma = self.recorder.manual_recording_active()
            if ma != getattr(self, "_last_manual", None):
                self._last_manual = ma
                if self.pages:
                    self.pages["home"].set_manual_ui(ma)
            if (
                self._recording
                and not self.recorder.manual_recording_active()
                and not self.recorder.buffer_alive()
            ):
                self._crash_count = getattr(self, "_crash_count", 0) + 1
            else:
                self._crash_count = 0
            if self.pages:
                self.pages["home"].update_buffer(self.recorder.buffer_seconds_filled())
                self.pages["home"].set_recording(self._recording)
            if self.rec_dot:
                self.rec_dot.configure(
                    text="\u23fa" if self._recording else "\u25a0",
                    text_color=theme.RED if self._recording else theme.TEXT_DIM,
                )
            if self._badge:
                self._badge.configure(
                    text=(
                        i18n.t("badge.live")
                        if self._recording
                        else i18n.t("badge.off")
                    ),
                    fg_color=theme.RED if self._recording else theme.VERSION_MUTED,
                )
            if self._tray_icon:
                ph = str(config.get("panel_hotkey")).upper()
                state = "Recording" if self._recording else "Paused"
                self._tray_icon.title = f"{config.APP_DISPLAY} — {state}  |  {ph}: panel"
        except Exception:
            pass
        self.after(1000, self._tick)

    def _show_toast(self, msg, color=None, duration=3500):
        try:
            import tkinter as tk

            if color is None:
                color = theme.TOAST_ACCENT
            t = tk.Toplevel(self)
            t.overrideredirect(True)
            t.attributes("-topmost", True)
            t.attributes("-alpha", 0.0)
            t.configure(bg=theme.TOAST_BG)
            pad_x, pad_y = 18, 10
            lbl = tk.Label(
                t,
                text=msg,
                fg=color,
                bg=theme.TOAST_BG,
                font=("Segoe UI", 12, "bold"),
                padx=pad_x,
                pady=pad_y,
            )
            lbl.pack()
            t.update_idletasks()
            w = t.winfo_reqwidth()
            h = t.winfo_reqheight()
            t.geometry(f"{w}x{h}+16+16")

            def _fade_in(alpha=0.0):
                alpha = min(alpha + 0.08, 0.92)
                try:
                    t.attributes("-alpha", alpha)
                except Exception:
                    return
                if alpha < 0.92:
                    t.after(18, lambda: _fade_in(alpha))

            _fade_in()

            def _fade_out(alpha=0.92):
                alpha = max(alpha - 0.08, 0.0)
                try:
                    t.attributes("-alpha", alpha)
                except Exception:
                    return
                if alpha > 0:
                    t.after(18, lambda: _fade_out(alpha))
                else:
                    try:
                        t.destroy()
                    except Exception:
                        pass

            t.after(duration, _fade_out)
        except Exception:
            pass

    def open_stats_window(self):
        try:
            if self._stats_win is not None and self._stats_win.winfo_exists():
                self._stats_win.destroy()
                return
        except Exception:
            self._stats_win = None
        if not any(
            (
                config.get("stats_show_cpu"),
                config.get("stats_show_ram"),
                config.get("stats_show_gpu"),
                config.get("stats_show_fps"),
            )
        ):
            try:
                self.pages["home"].show_info(
                    i18n.t("stats.none_enabled"), color=theme.WARNING
                )
            except Exception:
                pass
            return
        self._stats_win = StatsWindow(self, self.recorder, self)

    def toggle_manual_recording(self):
        if self.recorder.manual_recording_active():
            threading.Thread(target=self._manual_stop_thread, daemon=True).start()
        else:
            threading.Thread(target=self._manual_start_thread, daemon=True).start()

    def _manual_start_thread(self):
        if self.recorder.manual_recording_active():
            return
        if self.watchdog:
            self.watchdog.set_paused(True)
        self._resume_buffer_after_manual = self._recording
        self.recorder.stop()
        self.recorder.reset_buffer()
        od = config.get("output_dir")
        os.makedirs(od, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = os.path.join(od, f"manual_{ts}.mp4")
        ok = self.recorder.start_manual_recording(path)
        if not ok:
            self.after(
                0,
                lambda: self.pages["home"].show_info(
                    "Could not start file recording. See app.log.",
                    color=theme.RED,
                ),
            )
            if self._resume_buffer_after_manual:
                self.recorder.start()
            if self.watchdog:
                self.watchdog.set_paused(False)
            return
        self.after(0, lambda: self.pages["home"].set_manual_ui(True))
        self.after(
            0,
            lambda: self.pages["home"].show_info(
                "Recording to MP4… tap again to stop.", color=theme.TEXT_SOFT
            ),
        )

    def _manual_stop_thread(self):
        self.recorder.stop_manual_recording()
        if self._resume_buffer_after_manual:
            self.recorder.start()
        if self.watchdog:
            self.watchdog.set_paused(False)
        self.after(0, lambda: self.pages["home"].set_manual_ui(False))
        self.after(
            0,
            lambda: self.pages["home"].show_info("File recording finished.", color=theme.GREEN),
        )
        self.after(800, lambda: self.pages["home"].refresh_gallery())

    def do_save(self, event=None):
        """Hotkeys and UI may call from non-Tk threads; always marshal to main thread."""
        self.after(0, self._do_save_impl)

    def _do_save_impl(self):
        if not self.pages:
            return
        hp = self.pages["home"]
        if self.recorder.manual_recording_active():
            hp.show_info("Stop file recording before saving a replay clip.", color=theme.RED)
            return
        hp.show_info("Saving…", color=theme.TEXT_SOFT)
        self._show_toast("\u23fa  Saving…", color=theme.TEXT_SOFT, duration=8000)

        def ok(p):
            self.after(
                0, lambda: hp.show_info(f"\u2713 Saved: {os.path.basename(p)}")
            )
            self.after(
                0,
                lambda: self._show_toast(
                    f"\u2713  Saved  {os.path.basename(p)}", color=theme.GREEN, duration=4000
                ),
            )
            try:
                self.after(1500, hp.refresh_gallery)
            except Exception:
                pass

        def er(m):
            self.after(0, lambda: hp.show_info(f"\u2717 {m}", color=theme.RED))
            self.after(
                0,
                lambda: self._show_toast(f"\u2717  {m}", color=theme.RED, duration=5000),
            )

        saver_mod.save_replay(
            self.recorder, on_done=ok, on_error=er, watchdog=self.watchdog
        )

    def do_toggle(self, event=None):
        self.after(0, self._do_toggle_impl)

    def _do_toggle_impl(self):
        if self.recorder.manual_recording_active():
            if self.pages:
                self.pages["home"].show_info(
                    "Stop file recording first (same row).", color=theme.RED
                )
            return
        if self._recording:
            self._recording = False
            if self.overlay:
                self.overlay.hide()
            if self._tray_icon:
                self._tray_icon.icon = _ti(False)
            if self.pages:
                self.pages["home"].set_recording(False)

            def _stop_bg():
                if self.watchdog:
                    self.watchdog.set_paused(True)
                self.recorder.stop()
                self.recorder.reset_buffer()

            threading.Thread(target=_stop_bg, daemon=True).start()
        else:

            def _start_bg():
                import time as _t

                self.recorder.start()
                if self.watchdog:
                    self.watchdog.set_paused(False)
                _t.sleep(3)
                if self._recording and not self.recorder.buffer_alive():
                    _lp = os.path.join(config.APPDATA_DIR, "ffmpeg_stderr.log")
                    _msg = "\u26a0 ffmpeg failed to start"
                    try:
                        with open(_lp, "r", encoding="utf-8", errors="replace") as _f:
                            _ll = [ln.strip() for ln in _f.readlines() if ln.strip()]
                        if _ll:
                            _msg += ": " + _ll[-1][:80]
                    except Exception:
                        pass
                    self.after(
                        0, lambda: self.pages["home"].show_info(_msg, color=theme.RED)
                    )

            threading.Thread(target=_start_bg, daemon=True).start()
            self._recording = True
            if self.overlay:
                self.overlay.show()
            if self._tray_icon:
                self._tray_icon.icon = _ti(True)
            if self.pages:
                self.pages["home"].set_recording(True)

    def refresh_ui_language(self):
        if getattr(self, "_open_app_btn", None):
            self._open_app_btn.configure(text=i18n.t("nav.open_app"))
        if self.pages.get("home") and hasattr(self.pages["home"], "refresh_home_texts"):
            self.pages["home"].refresh_home_texts()

    def on_settings_saved(self):
        if self.pages:
            self.pages["home"].refresh_hotkeys()
            self.pages["home"].show_info(
                i18n.t("msg.settings_saved"), color=theme.TEXT_SOFT
            )
        try:
            if getattr(self, "_stats_win", None) and self._stats_win.winfo_exists():
                self._stats_win.destroy()
                self._stats_win = None
                if any(
                    (
                        config.get("stats_show_cpu"),
                        config.get("stats_show_ram"),
                        config.get("stats_show_gpu"),
                        config.get("stats_show_fps"),
                    )
                ):
                    self._stats_win = StatsWindow(self, self.recorder, self)
        except Exception:
            self._stats_win = None
        if self.overlay:
            self.overlay.toggle_enabled(config.get("overlay_enabled"))
        self.register_global_hotkeys()
        if self._recording:

            def _restart_bg():
                if self.watchdog:
                    self.watchdog.set_paused(True)
                self.recorder.stop()
                self.recorder.start()
                if self.watchdog:
                    self.watchdog.set_paused(False)

            threading.Thread(target=_restart_bg, daemon=True).start()
