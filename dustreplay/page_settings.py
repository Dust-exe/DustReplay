import os
import threading
import tkinter.filedialog as fd

import customtkinter as ctk

import config
import startup

_P = "#8833ee"
_PH = "#6622cc"
_PD = "#0e0018"

_NONE_MIC = "(No microphone)"
_NONE_SYS = "(No system audio)"

_ENC_LABELS = [
    "Auto (NVENC if available)",
    "NVIDIA NVENC only",
    "CPU H.264 (libx264)",
]
_ENC_VALUES = ["auto", "nvenc", "cpu"]


def _ffmpeg():
    p = os.path.join(config.APPDATA_DIR, "ffmpeg", "ffmpeg.exe")
    return p if os.path.isfile(p) else None


def _get_monitors():
    try:
        from monitors import list_monitors

        mons = list_monitors()
        if mons:
            return [m["name"] for m in mons]
    except Exception:
        pass
    return ["Display 1 (fallback)"]


def _get_audio_devices_bg(callback):
    import logging as _log

    _logger = _log.getLogger("settings.audio")

    def _run():
        try:
            from audio_devices import list_all_audio

            _ff = os.path.join(config.APPDATA_DIR, "ffmpeg", "ffmpeg.exe")
            if not os.path.isfile(_ff):
                _ff2 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ffmpeg", "ffmpeg.exe")
                _ff = _ff2 if os.path.isfile(_ff2) else "ffmpeg"
            _logger.info("ffmpeg for device list: %s", _ff)
            mic_items, sys_items = list_all_audio(_ff)
        except Exception as _e:
            _logger.error("Audio device list failed: %s", _e, exc_info=True)
            from audio_devices import LABEL_NO_MIC, LABEL_NO_SYS, LABEL_WIN_MIC, LABEL_WIN_SYS

            mic_items = [LABEL_NO_MIC, LABEL_WIN_MIC]
            sys_items = [LABEL_NO_SYS, LABEL_WIN_SYS]
        callback(mic_items, sys_items)

    threading.Thread(target=_run, daemon=True).start()


class SettingsPage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._v = {}
        self._mon_items = []
        self._mic_items = [_NONE_MIC]
        self._sys_items = [_NONE_SYS]
        self._mic_dd_widget = None
        self._sys_dd_widget = None
        self._build()
        self.after(300, self._load_audio_async)

    def _build(self):
        ctk.CTkLabel(
            self,
            text="\u2699\ufe0f  Settings",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="white",
        ).pack(pady=(22, 6), anchor="w", padx=26)

        self._scroll = ctk.CTkScrollableFrame(
            self, corner_radius=0, fg_color="#08080e", scrollbar_button_color=_P
        )
        self._scroll.pack(fill="both", expand=True, padx=0, pady=0)
        s = self._scroll

        self._sec(s, "\U0001f5a5\ufe0f  Display")
        self._monitor_dd(s)
        self._sec(s, "\U0001f3a5  Recording")
        self._encoder_dd(s)
        self._sld(s, "save_minutes", "Clip length to save (min)", 1, 10)
        self._sld(s, "buffer_minutes", "Rolling buffer (min)", 5, 60)
        self._sld(s, "fps", "Target FPS", 15, 60)
        self._sld(s, "quality", "Quality (lower = better, NVENC CQ / x264 CRF)", 18, 40)

        self._sec(s, "\U0001f3a7  Audio")
        self._audio_section(s)

        self._sec(s, "\u2328\ufe0f  Hotkeys")
        self._ent(s, "hotkey_save", "Save replay hotkey")
        self._ent(s, "hotkey_toggle", "Stop / start recording")
        self._ent(s, "panel_hotkey", "Toggle side panel")
        self._panel_side_dd(s)

        self._sec(s, "\U0001f4c2  Output folder")
        self._fld(s, "output_dir")

        self._sec(s, "\U0001f534  Indicator")
        self._tgl(
            s,
            "overlay_enabled",
            "Small REC pill (drag to move; position is saved)",
        )

        self._sec(s, "\U0001f4ca  Live stats panel (Home → Statistics)")
        self._tgl(s, "stats_show_target_fps", "Target FPS")
        self._tgl(s, "stats_show_display", "Display index")
        self._tgl(s, "stats_show_encoder", "Encoder (setting + pipeline)")
        self._tgl(s, "stats_show_buffer", "Buffer fill")
        self._tgl(s, "stats_show_capture_state", "Capture state (buffer / manual)")
        self._tgl(s, "stats_show_cpu", "CPU % (needs psutil)")
        self._tgl(s, "stats_show_ram", "RAM % (needs psutil)")
        self._tgl(s, "stats_show_disk", "Free disk on output drive")
        self._tgl(s, "stats_show_uptime", "App uptime (seconds)")

        self._sec(s, "\U0001f680  Startup")
        self._strt(s)

        ctk.CTkButton(
            self,
            text="\u2713  Save settings",
            height=44,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=_P,
            hover_color=_PH,
            corner_radius=12,
            command=self._save,
        ).pack(pady=(4, 16), padx=20, fill="x")

    def _encoder_dd(self, p):
        cur = (config.get("video_encoder") or "auto").lower()
        try:
            ix = _ENC_VALUES.index(cur)
        except ValueError:
            ix = 0
        r = ctk.CTkFrame(p, fg_color=_PD, corner_radius=8)
        r.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(
            r,
            text="Video encoder",
            anchor="w",
            text_color="#bbaadd",
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(12, 0), pady=12)
        self._enc_var = ctk.StringVar(value=_ENC_LABELS[ix])
        ctk.CTkOptionMenu(
            r,
            variable=self._enc_var,
            values=_ENC_LABELS,
            fg_color="#150030",
            button_color=_P,
            button_hover_color=_PH,
            dropdown_fg_color="#0e0018",
            width=220,
        ).pack(side="right", padx=12, pady=8)

    def _panel_side_dd(self, p):
        _side_opts = ["\u25c4 Left edge", "Right edge \u25ba"]
        _side_map = {"left": _side_opts[0], "right": _side_opts[1]}
        _side_rmap = {v: k for k, v in _side_map.items()}
        cur = _side_map.get(config.get("panel_side"), _side_opts[1])
        r = ctk.CTkFrame(p, fg_color=_PD, corner_radius=8)
        r.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(
            r,
            text="Panel side",
            anchor="w",
            text_color="#bbaadd",
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(12, 0), pady=12)
        self._side_var = ctk.StringVar(value=cur)
        self._side_rmap = _side_rmap
        ctk.CTkOptionMenu(
            r,
            variable=self._side_var,
            values=_side_opts,
            fg_color="#150030",
            button_color=_P,
            button_hover_color=_PH,
            dropdown_fg_color="#0e0018",
            width=160,
        ).pack(side="right", padx=12, pady=8)

    def _monitor_dd(self, p):
        self._mon_items = _get_monitors()
        cur_n = int(config.get("monitor_index") or 1)
        cur_n = max(1, min(cur_n, len(self._mon_items)))
        cur = self._mon_items[cur_n - 1]
        r = ctk.CTkFrame(p, fg_color=_PD, corner_radius=8)
        r.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(
            r,
            text="Capture display",
            anchor="w",
            text_color="#bbaadd",
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(12, 0), pady=12)
        self._mon_var = ctk.StringVar(value=cur)
        ctk.CTkOptionMenu(
            r,
            variable=self._mon_var,
            values=self._mon_items,
            fg_color="#150030",
            button_color=_P,
            button_hover_color=_PH,
            dropdown_fg_color="#0e0018",
            width=220,
        ).pack(side="right", padx=12, pady=8)

    def _audio_section(self, p):
        r1 = ctk.CTkFrame(p, fg_color=_PD, corner_radius=8)
        r1.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(
            r1,
            text="\U0001f3a7  Microphone",
            anchor="w",
            text_color="#bbaadd",
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(12, 0), pady=12)
        self._mic_var = ctk.StringVar(value=_NONE_MIC)
        self._mic_dd_widget = ctk.CTkOptionMenu(
            r1,
            variable=self._mic_var,
            values=self._mic_items,
            fg_color="#150030",
            button_color=_P,
            button_hover_color=_PH,
            dropdown_fg_color="#0e0018",
            width=220,
        )
        self._mic_dd_widget.pack(side="right", padx=12, pady=8)

        r2 = ctk.CTkFrame(p, fg_color=_PD, corner_radius=8)
        r2.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(
            r2,
            text="\U0001f50a  System audio",
            anchor="w",
            text_color="#bbaadd",
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(12, 0), pady=12)
        self._sys_var = ctk.StringVar(value=_NONE_SYS)
        self._sys_dd_widget = ctk.CTkOptionMenu(
            r2,
            variable=self._sys_var,
            values=self._sys_items,
            fg_color="#150030",
            button_color=_P,
            button_hover_color=_PH,
            dropdown_fg_color="#0e0018",
            width=220,
        )
        self._sys_dd_widget.pack(side="right", padx=12, pady=8)

        hint_row = ctk.CTkFrame(p, fg_color="transparent")
        hint_row.pack(fill="x", padx=14, pady=(2, 4))
        self._audio_hint = ctk.CTkLabel(
            hint_row,
            text="  \u23f3 Loading audio devices…",
            font=ctk.CTkFont(size=11),
            text_color="#554477",
        )
        self._audio_hint.pack(side="left", anchor="w")
        self._audio_refresh_btn = ctk.CTkButton(
            hint_row,
            text="\u27f3 Refresh",
            width=72,
            fg_color="#150030",
            hover_color=_PH,
            border_width=1,
            border_color=_P,
            font=ctk.CTkFont(size=11),
            command=self._refresh_audio,
        )
        self._audio_refresh_btn.pack(side="right")

    def _load_audio_async(self):
        def on_done(mic_devs, sys_devs):
            self.after(0, lambda: self._apply_audio_devices(mic_devs, sys_devs))

        _get_audio_devices_bg(on_done)

    def _refresh_audio(self):
        if self._audio_hint:
            self._audio_hint.configure(text="  \u23f3 Refreshing…", text_color="#554477")
        self._load_audio_async()

    def _apply_audio_devices(self, mic_items, sys_items):
        try:
            from audio_devices import config_to_label

            self._mic_items = mic_items
            self._sys_items = sys_items

            saved_mic = config.get("mic_device") or ""
            mic_cur = config_to_label(saved_mic, "mic")
            if mic_cur not in mic_items:
                mic_cur = mic_items[0]
            if self._mic_dd_widget:
                self._mic_dd_widget.configure(values=mic_items)
                self._mic_var.set(mic_cur)

            saved_sys = config.get("sys_audio_device") or ""
            sys_cur = config_to_label(saved_sys, "sys")
            if sys_cur not in sys_items:
                sys_cur = sys_items[0]
            if self._sys_dd_widget:
                self._sys_dd_widget.configure(values=sys_items)
                self._sys_var.set(sys_cur)

            n = max(0, len(mic_items) - 2)
            if self._audio_hint:
                self._audio_hint.configure(
                    text=f"  \u2713 {n} device(s) found." if n > 0 else "  \u26a0 Limited devices. Try Refresh.",
                    text_color="#554477" if n > 0 else "#886600",
                )
        except Exception:
            pass

    def _sec(self, p, t):
        ctk.CTkLabel(
            p, text=t, font=ctk.CTkFont(size=12, weight="bold"), text_color="#9944ee"
        ).pack(anchor="w", padx=12, pady=(20, 2))
        ctk.CTkFrame(p, height=1, fg_color="#220044").pack(fill="x", padx=8, pady=(0, 6))

    def _sld(self, p, k, l, f, t):
        v = ctk.IntVar(value=int(config.get(k)))
        self._v[k] = (v, int)
        r = ctk.CTkFrame(p, fg_color=_PD, corner_radius=8)
        r.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(
            r, text=l, anchor="w", text_color="#bbaadd", font=ctk.CTkFont(size=12)
        ).pack(side="left", padx=(12, 0), pady=12)
        lb = ctk.CTkLabel(
            r, text=str(v.get()), width=40, text_color="white", font=ctk.CTkFont(size=13, weight="bold")
        )
        lb.pack(side="right", padx=(0, 12))
        ctk.CTkSlider(
            r,
            variable=v,
            from_=f,
            to=t,
            number_of_steps=t - f,
            button_color=_P,
            button_hover_color=_PH,
            progress_color=_P,
            height=14,
            command=lambda x, lb=lb: lb.configure(text=str(int(float(x)))),
        ).pack(side="right", padx=6, fill="x", expand=True)

    def _tgl(self, p, k, l):
        v = ctk.BooleanVar(value=bool(config.get(k)))
        self._v[k] = (v, bool)
        r = ctk.CTkFrame(p, fg_color=_PD, corner_radius=8)
        r.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(
            r,
            text=l,
            anchor="w",
            text_color="#bbaadd",
            font=ctk.CTkFont(size=12),
            wraplength=220,
        ).pack(side="left", padx=(12, 0), pady=12)
        ctk.CTkSwitch(
            r,
            variable=v,
            text="",
            button_color=_P,
            button_hover_color=_PH,
            progress_color=_P,
        ).pack(side="right", padx=12)

    def _ent(self, p, k, l):
        v = ctk.StringVar(value=str(config.get(k)))
        self._v[k] = (v, str)
        r = ctk.CTkFrame(p, fg_color=_PD, corner_radius=8)
        r.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(
            r,
            text=l,
            anchor="w",
            text_color="#bbaadd",
            font=ctk.CTkFont(size=12),
            wraplength=180,
        ).pack(side="left", padx=(12, 0), pady=12)
        ctk.CTkEntry(
            r, textvariable=v, width=110, border_color=_P, fg_color="#050510"
        ).pack(side="right", padx=12, pady=8)

    def _fld(self, p, k):
        v = ctk.StringVar(value=str(config.get(k)))
        self._v[k] = (v, str)
        r = ctk.CTkFrame(p, fg_color=_PD, corner_radius=8)
        r.pack(fill="x", padx=8, pady=4)
        ctk.CTkEntry(
            r, textvariable=v, border_color="#330055", fg_color="#050510"
        ).pack(side="left", fill="x", expand=True, padx=(12, 6), pady=10)
        ctk.CTkButton(
            r,
            text="Browse",
            width=68,
            fg_color="#150030",
            hover_color=_PH,
            border_width=1,
            border_color=_P,
            command=lambda: (lambda x: v.set(x) if x else None)(
                fd.askdirectory(initialdir=v.get())
            ),
        ).pack(side="right", padx=(0, 12))

    def _strt(self, p):
        reg = startup.is_registered()
        r = ctk.CTkFrame(p, fg_color=_PD, corner_radius=10)
        r.pack(fill="x", padx=6, pady=3)
        self._sl = ctk.CTkLabel(
            r,
            text="\u2713 Run at logon (Task Scheduler)" if reg else "\u2715 Not registered for logon",
            text_color="#4caf50" if reg else "#888",
            anchor="w",
            font=ctk.CTkFont(size=12),
        )
        self._sl.pack(side="left", padx=(14, 0), pady=10)
        ctk.CTkButton(
            r,
            text="Toggle",
            width=90,
            fg_color="#2a004a",
            hover_color=_PH,
            border_width=1,
            border_color=_P,
            command=self._ts,
        ).pack(side="right", padx=14)

    def _ts(self):
        if startup.is_registered():
            startup.unregister()
            self._sl.configure(text="\u2715 Not registered for logon", text_color="#888")
        else:
            if startup.register():
                self._sl.configure(
                    text="\u2713 Run at logon (Task Scheduler)", text_color="#4caf50"
                )

    def _save(self):
        mon_sel = self._mon_var.get()
        if mon_sel in self._mon_items:
            mon_idx = self._mon_items.index(mon_sel) + 1
        else:
            mon_idx = 1
        config.set("monitor_index", mon_idx)

        try:
            ei = _ENC_LABELS.index(self._enc_var.get())
            config.set("video_encoder", _ENC_VALUES[ei])
        except ValueError:
            config.set("video_encoder", "auto")

        from audio_devices import label_to_config

        config.set("mic_device", label_to_config(self._mic_var.get(), "mic"))
        config.set("sys_audio_device", label_to_config(self._sys_var.get(), "sys"))
        config.set("panel_side", self._side_rmap.get(self._side_var.get(), "right"))

        for k, (v, c) in self._v.items():
            try:
                config.set(k, c(v.get()))
            except Exception:
                pass

        config.save()
        self.app.on_settings_saved()
