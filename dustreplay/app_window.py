import logging
import os
import threading
from datetime import datetime

import customtkinter as ctk
import pystray
from PIL import Image, ImageDraw

import config
import i18n
import startup
from overlay import RecordingOverlay
from page_home import HomePage
from page_recordings import RecordingsPage
from page_settings import SettingsPage
import saver as saver_mod
from stats_window import StatsWindow

logger = logging.getLogger(__name__)

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

_P = "#8833ee"
_PH = "#6622cc"
_BG = "#050508"
_CBG = "#08080e"
_SBG = "#000000"
_PANEL_W = 340


def _ti(rec):
    sz = 64
    img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([2, 2, sz - 2, sz - 2], fill=(20, 0, 40, 220))
    d.ellipse([14, 14, sz - 14, sz - 14], fill=(220, 50, 50) if rec else (80, 80, 80))
    if rec:
        d.ellipse([26, 26, sz - 26, sz - 26], fill=(255, 80, 80))
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
        p.configure(fg_color=_BG)
        _init_x = 0 if config.get("panel_side") == "left" else sw - _PANEL_W
        p.geometry(f"{_PANEL_W}x{sh}+{_init_x}+0")
        p.resizable(False, False)
        self._panel = p

        hdr = ctk.CTkFrame(p, fg_color=_SBG, corner_radius=0, height=52)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(
            hdr,
            text="\u25cf  DustReplay",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=_P,
        ).pack(side="left", padx=12, pady=14)
        self._badge = ctk.CTkLabel(
            hdr,
            text="LIVE",
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color="white",
            fg_color="#e03030",
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
            fg_color="#1a003a",
            hover_color="#3d1080",
            corner_radius=6,
            font=ctk.CTkFont(size=13),
            command=self.toggle_panel,
        ).pack(side="right", padx=8)
        self.rec_dot = ctk.CTkLabel(
            hdr, text="\u23fa", font=ctk.CTkFont(size=11), text_color="#e03030"
        )
        self.rec_dot.pack(side="right", padx=2)
        ctk.CTkFrame(p, height=1, fg_color="#2a0050").pack(fill="x")

        nav = ctk.CTkFrame(p, fg_color=_SBG, corner_radius=0, height=40)
        nav.pack(fill="x")
        nav.pack_propagate(False)
        for label_key, key in (
            ("nav.home", "home"),
            ("nav.clips", "recordings"),
            ("nav.settings", "settings"),
        ):
            label = i18n.t(label_key)
            b = ctk.CTkButton(
                nav,
                text=label,
                width=(_PANEL_W - 16) // 3,
                height=30,
                fg_color="transparent",
                hover_color="#1e003a",
                text_color="#ccaaff",
                font=ctk.CTkFont(size=11),
                corner_radius=6,
                command=lambda k=key: self.sp(k),
            )
            b.pack(side="left", padx=2, pady=5)
            self._nb[key] = b
        ctk.CTkFrame(p, height=1, fg_color="#2a0050").pack(fill="x")

        self.content = ctk.CTkFrame(p, corner_radius=0, fg_color=_CBG)
        self.content.pack(fill="both", expand=True)
        self.pages = {
            "home": HomePage(self.content, app=self),
            "recordings": RecordingsPage(self.content, app=self),
            "settings": SettingsPage(self.content, app=self),
        }
        for pg in self.pages.values():
            pg.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.sp("home")
        self.refresh_ui_language()

        from version import __version__

        ctk.CTkLabel(
            p,
            text=f"v{__version__}",
            font=ctk.CTkFont(size=10),
            text_color="#2a0050",
            fg_color=_BG,
        ).pack(side="bottom", pady=4)

    def sp(self, key):
        for k, pg in self.pages.items():
            if k == key:
                pg.place(relx=0, rely=0, relwidth=1, relheight=1)
            else:
                pg.place_forget()
        for k, b in self._nb.items():
            b.configure(
                fg_color=_P if k == key else "transparent",
                text_color="white" if k == key else "#ccaaff",
            )

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

    def _on_panel_focus_out(self, event=None):
        if not self._panel_visible:
            return
        self.after(120, self._check_panel_focus_lost)

    def _check_panel_focus_lost(self):
        if not self._panel_visible or not self._panel:
            return
        w = self.focus_get()
        try:
            if w is None:
                self._hide_panel()
                return
            if w.winfo_toplevel() == self._panel:
                return
        except Exception:
            pass
        self._hide_panel()

    def _hide_panel(self):
        self._destroy_panel_backdrop()
        if self._panel:
            try:
                self._panel.unbind("<FocusOut>")
            except Exception:
                pass
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
        bd.attributes("-alpha", 0.0)
        bd.configure(bg="#000010")
        bd.geometry(f"{sw}x{sh}+0+0")
        bd.attributes("-topmost", True)
        bd.bind("<Button-1>", self._close_panel_from_outside)
        self._panel_backdrop = bd

        def _fade_bd(step=0):
            a = min(0.14, (step + 1) * 0.035)
            try:
                bd.attributes("-alpha", a)
            except Exception:
                return
            if a < 0.135:
                bd.after(14, lambda: _fade_bd(step + 1))

        _fade_bd(0)

        x = self._panel_x()
        self._panel.geometry(f"{_PANEL_W}x{sh}+{x}+0")
        self._panel.update_idletasks()
        self._panel.deiconify()
        self._panel.lift()
        self._panel.attributes("-topmost", True)
        try:
            self._panel.attributes("-alpha", 0.0)
        except Exception:
            pass

        def _fade_panel(pa=0.0):
            np = min(1.0, pa + 0.2)
            try:
                self._panel.attributes("-alpha", np)
            except Exception:
                pass
            if np < 1.0:
                self._panel.after(18, lambda: _fade_panel(np))

        _fade_panel(0.0)
        self._panel.focus_force()
        self._panel.bind("<FocusOut>", self._on_panel_focus_out)
        self._panel_visible = True

    def _btray(self):
        ph = str(config.get("panel_hotkey")).upper()
        menu = pystray.Menu(
            pystray.MenuItem(
                "Show / hide panel",
                lambda i, it: self.after(0, self.toggle_panel),
                default=True,
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
                "DustReplay",
                _ti(True),
                f"DustReplay  |  {ph}: panel",
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
                    text_color="#e03030" if self._recording else "#555",
                )
            if self._badge:
                self._badge.configure(
                    text=(
                        i18n.t("badge.live")
                        if self._recording
                        else i18n.t("badge.off")
                    ),
                    fg_color="#e03030" if self._recording else "#444",
                )
            if self._tray_icon:
                ph = str(config.get("panel_hotkey")).upper()
                state = "Recording" if self._recording else "Paused"
                self._tray_icon.title = f"DustReplay — {state}  |  {ph}: panel"
        except Exception:
            pass
        self.after(1000, self._tick)

    def _show_toast(self, msg, color="#ccaaff", duration=3500):
        try:
            import tkinter as tk

            t = tk.Toplevel(self)
            t.overrideredirect(True)
            t.attributes("-topmost", True)
            t.attributes("-alpha", 0.0)
            t.configure(bg="#0d001f")
            pad_x, pad_y = 18, 10
            lbl = tk.Label(
                t,
                text=msg,
                fg=color,
                bg="#0d001f",
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
            if self._stats_win and self._stats_win.winfo_exists():
                self._stats_win.focus_force()
                return
        except Exception:
            self._stats_win = None
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
                    color="#e03030",
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
                "Recording to MP4… tap again to stop.", color="#aa88ff"
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
            lambda: self.pages["home"].show_info("File recording finished.", color="#4caf50"),
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
            hp.show_info("Stop file recording before saving a replay clip.", color="#e03030")
            return
        hp.show_info("Saving…", color="#aa88ff")
        self._show_toast("\u23fa  Saving…", color="#aa88ff", duration=8000)

        def ok(p):
            self.after(
                0, lambda: hp.show_info(f"\u2713 Saved: {os.path.basename(p)}")
            )
            self.after(
                0,
                lambda: self._show_toast(
                    f"\u2713  Saved  {os.path.basename(p)}", color="#44ee88", duration=4000
                ),
            )
            # Do NOT reset_buffer here: it deletes ALL seg_*.mp4 including the new
            # rolling buffer ffmpeg just started after cut_and_get_segments.
            # saver.py removes only the merged segment files after export.
            try:
                self.after(1500, hp.refresh_gallery)
            except Exception:
                pass

        def er(m):
            self.after(0, lambda: hp.show_info(f"\u2717 {m}", color="#e03030"))
            self.after(
                0,
                lambda: self._show_toast(f"\u2717  {m}", color="#e03030", duration=5000),
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
                    "Stop file recording first (same row).", color="#e03030"
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
                        0, lambda: self.pages["home"].show_info(_msg, color="#e03030")
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
        if not getattr(self, "_nb", None):
            return
        self._nb["home"].configure(text=i18n.t("nav.home"))
        self._nb["recordings"].configure(text=i18n.t("nav.clips"))
        self._nb["settings"].configure(text=i18n.t("nav.settings"))
        if self.pages.get("home") and hasattr(self.pages["home"], "refresh_home_texts"):
            self.pages["home"].refresh_home_texts()

    def on_settings_saved(self):
        if self.pages:
            self.pages["home"].refresh_hotkeys()
            self.pages["home"].show_info(
                i18n.t("msg.settings_saved"), color="#aa88ff"
            )
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
