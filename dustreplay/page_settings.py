import os
import threading
import tkinter.filedialog as fd

import customtkinter as ctk

import config
import i18n
import startup
import theme

_P = theme.P
_PH = theme.PH
_PD = theme.PD

_NONE_MIC = "(No microphone)"
_NONE_SYS = "(No system audio)"

_ENC_VALUES = ["auto", "nvenc", "amf", "cpu"]
_PROFILE_VALUES = ["balanced", "low_gpu"]
_BACKEND_VALUES = ["ddagrab", "gdigrab"]
_GAME_MODE_VALUES = ["off", "auto", "on"]
_RES_CAP_VALUES = (0, 1440, 1080, 720)
_FLIP_VALUES = ("none", "vertical", "horizontal", "rotate180")

_STATS_CORNER_ORDER = ("tl", "tr", "bl", "br")
_IND_CORNER_ORDER = ("tl", "tr", "bl", "br")
_STATS_MODE_ORDER = ("compact", "normal", "advanced")


def _ffmpeg():
    return config.resolve_ffmpeg_exe()


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

            _ff = config.resolve_ffmpeg_exe() or "ffmpeg"
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
        self._lang_var = None
        self._rebuild()
        self.after(300, self._load_audio_async)

    def _rebuild(self):
        for w in self.winfo_children():
            w.destroy()
        self._v = {}

        ctk.CTkLabel(
            self,
            text=i18n.t("settings.title"),
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="white",
        ).pack(pady=(22, 6), anchor="w", padx=26)

        self._scroll = ctk.CTkScrollableFrame(
            self, corner_radius=0, fg_color=theme.BG, scrollbar_button_color=_P
        )
        self._scroll.pack(fill="both", expand=True, padx=0, pady=0)
        s = self._scroll

        self._sec(s, "sec.display")
        self._monitor_dd(s)
        self._flip_dd(s)
        self._sec(s, "sec.recording")
        self._encoder_dd(s)
        self._buffer_profile_dd(s)
        self._capture_backend_dd(s)
        self._game_mode_dd(s)
        self._sld(s, "buffer_minutes", "rec.buffer", 5, 60, "rec.buffer.hint")
        self._sld(s, "fps", "rec.fps", 10, 60, "rec.fps.hint")
        self._sld(s, "quality", "rec.quality", 18, 40, "rec.quality.hint")
        self._res_cap_dd(s)

        self._sec(s, "sec.audio")
        self._audio_section(s)

        self._sec(s, "sec.hotkeys")
        self._ent(s, "hotkey_save", "hk.save")
        self._ent(s, "hotkey_toggle", "hk.toggle")
        self._ent(s, "panel_hotkey", "hk.panel")
        self._panel_side_dd(s)

        self._sec(s, "sec.output")
        self._fld(s, "output_dir")

        self._sec(s, "sec.indicator")
        self._tgl(s, "overlay_enabled", "ind.rec")
        self._overlay_ind_corner_dd(s)

        self._sec(s, "sec.hardware")
        self._tgl(s, "stats_show_cpu", "hw.cpu")
        self._tgl(s, "stats_show_ram", "hw.ram")
        self._tgl(s, "stats_show_gpu", "hw.gpu")
        self._tgl(s, "stats_show_fps", "hw.fps")
        self._stats_mode_dd(s)
        self._stats_corner_dd(s)

        self._sec(s, "sec.startup")
        self._strt(s)

        from updater import check_for_updates
        ctk.CTkButton(
            s,
            text="Check for Updates",
            height=32,
            fg_color=theme.PANEL,
            hover_color=_PH,
            border_width=1,
            border_color=_P,
            command=lambda: check_for_updates(app=self.app, manual=True),
        ).pack(pady=(10, 0), padx=14, fill="x")

        lang_fr = ctk.CTkFrame(self, fg_color=theme.PANEL, corner_radius=10)
        lang_fr.pack(fill="x", padx=16, pady=(10, 6))
        ctk.CTkLabel(
            lang_fr,
            text=i18n.t("settings.language"),
            anchor="w",
            text_color=theme.TEXT_SOFT,
            font=ctk.CTkFont(size=13, weight="bold"),
        ).pack(side="left", padx=(14, 8), pady=12)
        cur = (config.get("ui_language") or "en").lower()
        init = "English" if cur != "tr" else "Türkçe"
        self._lang_var = ctk.StringVar(value=init)
        ctk.CTkOptionMenu(
            lang_fr,
            variable=self._lang_var,
            values=["English", "Türkçe"],
            command=self._on_language,
            fg_color=theme.PANEL,
            button_color=_P,
            button_hover_color=_PH,
            dropdown_fg_color=theme.ACCENT_DEEP,
            width=160,
        ).pack(side="right", padx=14, pady=10)

        ctk.CTkButton(
            self,
            text=i18n.t("settings.save"),
            height=44,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color=_P,
            hover_color=_PH,
            corner_radius=12,
            command=self._save,
        ).pack(pady=(4, 16), padx=20, fill="x")

    def _on_language(self, choice):
        config.set("ui_language", "tr" if choice == "Türkçe" else "en")
        config.save()
        self._rebuild()
        self.after(200, self._load_audio_async)
        if self.app:
            self.app.refresh_ui_language()

    def _overlay_ind_corner_dd(self, p):
        self._ind_corner_codes = list(_IND_CORNER_ORDER)
        self._ind_corner_labels = [
            i18n.t(f"hw.corner_{c}") for c in self._ind_corner_codes
        ]
        cur = (config.get("overlay_corner") or "tr").lower()
        if cur not in self._ind_corner_codes:
            cur = "tr"
        cur_label = self._ind_corner_labels[self._ind_corner_codes.index(cur)]
        r = ctk.CTkFrame(p, fg_color=_PD, corner_radius=8)
        r.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(
            r,
            text=i18n.t("ind.corner"),
            anchor="w",
            text_color=theme.TEXT_SOFT,
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(12, 0), pady=12)
        self._ind_corner_var = ctk.StringVar(value=cur_label)
        ctk.CTkOptionMenu(
            r,
            variable=self._ind_corner_var,
            values=self._ind_corner_labels,
            fg_color=theme.PANEL,
            button_color=_P,
            button_hover_color=_PH,
            dropdown_fg_color=theme.ACCENT_DEEP,
            width=200,
        ).pack(side="right", padx=12, pady=8)
        hr = ctk.CTkFrame(p, fg_color="transparent")
        hr.pack(fill="x", padx=14, pady=(0, 4))
        ctk.CTkLabel(
            hr,
            text=i18n.t("ind.corner.hint"),
            anchor="w",
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_DIM,
            wraplength=420,
            justify="left",
        ).pack(side="left")

    def _stats_mode_dd(self, p):
        self._stats_mode_codes = list(_STATS_MODE_ORDER)
        self._stats_mode_labels = [i18n.t(f"hw.mode_{c}") for c in self._stats_mode_codes]
        cur = (config.get("stats_overlay_mode") or "normal").lower()
        if cur not in self._stats_mode_codes:
            cur = "normal"
        cur_label = self._stats_mode_labels[self._stats_mode_codes.index(cur)]
        r = ctk.CTkFrame(p, fg_color=_PD, corner_radius=8)
        r.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(
            r,
            text=i18n.t("hw.mode"),
            anchor="w",
            text_color=theme.TEXT_SOFT,
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(12, 0), pady=12)
        self._stats_mode_var = ctk.StringVar(value=cur_label)
        ctk.CTkOptionMenu(
            r,
            variable=self._stats_mode_var,
            values=self._stats_mode_labels,
            fg_color=theme.PANEL,
            button_color=_P,
            button_hover_color=_PH,
            dropdown_fg_color=theme.ACCENT_DEEP,
            width=200,
        ).pack(side="right", padx=12, pady=8)

    def _stats_corner_dd(self, p):
        self._stats_corner_codes = list(_STATS_CORNER_ORDER)
        self._stats_corner_labels = [
            i18n.t(f"hw.corner_{c}") for c in self._stats_corner_codes
        ]
        cur = (config.get("stats_overlay_corner") or "br").lower()
        if cur not in self._stats_corner_codes:
            cur = "br"
        cur_label = self._stats_corner_labels[self._stats_corner_codes.index(cur)]
        r = ctk.CTkFrame(p, fg_color=_PD, corner_radius=8)
        r.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(
            r,
            text=i18n.t("hw.corner"),
            anchor="w",
            text_color=theme.TEXT_SOFT,
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(12, 0), pady=12)
        self._stats_corner_var = ctk.StringVar(value=cur_label)
        ctk.CTkOptionMenu(
            r,
            variable=self._stats_corner_var,
            values=self._stats_corner_labels,
            fg_color=theme.PANEL,
            button_color=_P,
            button_hover_color=_PH,
            dropdown_fg_color=theme.ACCENT_DEEP,
            width=200,
        ).pack(side="right", padx=12, pady=8)

    def _encoder_dd(self, p):
        labels = i18n.encoder_labels()
        cur = (config.get("video_encoder") or "auto").lower()
        try:
            ix = _ENC_VALUES.index(cur)
        except ValueError:
            ix = 0
        r = ctk.CTkFrame(p, fg_color=_PD, corner_radius=8)
        r.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(
            r,
            text=i18n.t("rec.encoder"),
            anchor="w",
            text_color=theme.TEXT_SOFT,
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(12, 0), pady=12)
        self._enc_var = ctk.StringVar(value=labels[ix])
        ctk.CTkOptionMenu(
            r,
            variable=self._enc_var,
            values=labels,
            fg_color=theme.PANEL,
            button_color=_P,
            button_hover_color=_PH,
            dropdown_fg_color=theme.ACCENT_DEEP,
            width=220,
        ).pack(side="right", padx=12, pady=8)

    def _buffer_profile_dd(self, p):
        labels = i18n.buffer_profile_labels()
        cur = (config.get("buffer_encoder_profile") or "balanced").lower()
        try:
            ix = _PROFILE_VALUES.index(cur)
        except ValueError:
            ix = 0
        r = ctk.CTkFrame(p, fg_color=_PD, corner_radius=8)
        r.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(
            r,
            text=i18n.t("enc.profile"),
            anchor="w",
            text_color=theme.TEXT_SOFT,
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(12, 0), pady=12)
        self._profile_var = ctk.StringVar(value=labels[ix])
        ctk.CTkOptionMenu(
            r,
            variable=self._profile_var,
            values=labels,
            fg_color=theme.PANEL,
            button_color=_P,
            button_hover_color=_PH,
            dropdown_fg_color=theme.ACCENT_DEEP,
            width=220,
        ).pack(side="right", padx=12, pady=8)

    def _capture_backend_dd(self, p):
        labels = i18n.capture_backend_labels()
        cur = (config.get("capture_backend") or "ddagrab").lower()
        try:
            ix = _BACKEND_VALUES.index(cur)
        except ValueError:
            ix = 0
        r = ctk.CTkFrame(p, fg_color=_PD, corner_radius=8)
        r.pack(fill="x", padx=8, pady=4)
        tf = ctk.CTkFrame(r, fg_color="transparent")
        tf.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=8)
        ctk.CTkLabel(
            tf,
            text=i18n.t("rec.capture_backend"),
            anchor="w",
            text_color=theme.TEXT_SOFT,
            font=ctk.CTkFont(size=12),
        ).pack(fill="x")
        ctk.CTkLabel(
            tf,
            text=i18n.t("rec.capture_backend.hint"),
            anchor="w",
            text_color=theme.TEXT_DIM,
            font=ctk.CTkFont(size=10),
            wraplength=280,
        ).pack(fill="x")
        self._backend_var = ctk.StringVar(value=labels[ix])
        ctk.CTkOptionMenu(
            r,
            variable=self._backend_var,
            values=labels,
            fg_color=theme.PANEL,
            button_color=_P,
            button_hover_color=_PH,
            dropdown_fg_color=theme.ACCENT_DEEP,
            width=200,
        ).pack(side="right", padx=12, pady=8)

    def _game_mode_dd(self, p):
        labels = i18n.game_mode_labels()
        cur = (config.get("game_mode") or "auto").lower()
        try:
            ix = _GAME_MODE_VALUES.index(cur)
        except ValueError:
            ix = 1
        r = ctk.CTkFrame(p, fg_color=_PD, corner_radius=8)
        r.pack(fill="x", padx=8, pady=4)
        tf = ctk.CTkFrame(r, fg_color="transparent")
        tf.pack(side="left", fill="both", expand=True, padx=(12, 0), pady=8)
        ctk.CTkLabel(
            tf,
            text=i18n.t("rec.game_mode"),
            anchor="w",
            text_color=theme.TEXT_SOFT,
            font=ctk.CTkFont(size=12),
        ).pack(fill="x")
        ctk.CTkLabel(
            tf,
            text=i18n.t("rec.game_mode.hint"),
            anchor="w",
            text_color=theme.TEXT_DIM,
            font=ctk.CTkFont(size=10),
            wraplength=280,
        ).pack(fill="x")
        self._game_mode_var = ctk.StringVar(value=labels[ix])
        ctk.CTkOptionMenu(
            r,
            variable=self._game_mode_var,
            values=labels,
            fg_color=theme.PANEL,
            button_color=_P,
            button_hover_color=_PH,
            dropdown_fg_color=theme.ACCENT_DEEP,
            width=200,
        ).pack(side="right", padx=12, pady=8)

    def _panel_side_dd(self, p):
        labels = i18n.panel_side_labels()
        cur_side = config.get("panel_side") or "right"
        cur = labels[0] if cur_side == "left" else labels[1]
        r = ctk.CTkFrame(p, fg_color=_PD, corner_radius=8)
        r.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(
            r,
            text=i18n.t("panel.side"),
            anchor="w",
            text_color=theme.TEXT_SOFT,
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(12, 0), pady=12)
        self._side_var = ctk.StringVar(value=cur)
        self._panel_labels = labels
        ctk.CTkOptionMenu(
            r,
            variable=self._side_var,
            values=labels,
            fg_color=theme.PANEL,
            button_color=_P,
            button_hover_color=_PH,
            dropdown_fg_color=theme.ACCENT_DEEP,
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
            text=i18n.t("disp.capture"),
            anchor="w",
            text_color=theme.TEXT_SOFT,
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(12, 0), pady=12)
        self._mon_var = ctk.StringVar(value=cur)
        ctk.CTkOptionMenu(
            r,
            variable=self._mon_var,
            values=self._mon_items,
            fg_color=theme.PANEL,
            button_color=_P,
            button_hover_color=_PH,
            dropdown_fg_color=theme.ACCENT_DEEP,
            width=220,
        ).pack(side="right", padx=12, pady=8)

    def _res_cap_dd(self, p):
        labels = i18n.res_cap_labels()
        try:
            cur_h = int(config.get("capture_max_height"))
        except (TypeError, ValueError):
            cur_h = 0
        if cur_h not in _RES_CAP_VALUES:
            cur_h = 0
        cur_label = labels[_RES_CAP_VALUES.index(cur_h)]
        r = ctk.CTkFrame(p, fg_color=_PD, corner_radius=8)
        r.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(
            r,
            text=i18n.t("rec.res_cap"),
            anchor="w",
            text_color=theme.TEXT_SOFT,
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(12, 0), pady=12)
        self._res_cap_var = ctk.StringVar(value=cur_label)
        ctk.CTkOptionMenu(
            r,
            variable=self._res_cap_var,
            values=labels,
            fg_color=theme.PANEL,
            button_color=_P,
            button_hover_color=_PH,
            dropdown_fg_color=theme.ACCENT_DEEP,
            width=240,
        ).pack(side="right", padx=12, pady=8)
        hr = ctk.CTkFrame(p, fg_color="transparent")
        hr.pack(fill="x", padx=14, pady=(0, 4))
        ctk.CTkLabel(
            hr,
            text=i18n.t("rec.res_cap.hint"),
            anchor="w",
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_DIM,
            wraplength=420,
            justify="left",
        ).pack(side="left")

    def _flip_dd(self, p):
        labels = i18n.flip_labels()
        cur = (config.get("capture_flip") or "none").lower().strip()
        if cur not in _FLIP_VALUES:
            cur = "none"
        cur_label = labels[_FLIP_VALUES.index(cur)]
        r = ctk.CTkFrame(p, fg_color=_PD, corner_radius=8)
        r.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(
            r,
            text=i18n.t("disp.flip"),
            anchor="w",
            text_color=theme.TEXT_SOFT,
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(12, 0), pady=12)
        self._flip_var = ctk.StringVar(value=cur_label)
        ctk.CTkOptionMenu(
            r,
            variable=self._flip_var,
            values=labels,
            fg_color=theme.PANEL,
            button_color=_P,
            button_hover_color=_PH,
            dropdown_fg_color=theme.ACCENT_DEEP,
            width=240,
        ).pack(side="right", padx=12, pady=8)
        hr = ctk.CTkFrame(p, fg_color="transparent")
        hr.pack(fill="x", padx=14, pady=(0, 4))
        ctk.CTkLabel(
            hr,
            text=i18n.t("disp.flip.hint"),
            anchor="w",
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_DIM,
            wraplength=420,
            justify="left",
        ).pack(side="left")

    def _audio_section(self, p):
        r1 = ctk.CTkFrame(p, fg_color=_PD, corner_radius=8)
        r1.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(
            r1,
            text=i18n.t("audio.mic"),
            anchor="w",
            text_color=theme.TEXT_SOFT,
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(12, 0), pady=12)
        self._mic_var = ctk.StringVar(value=_NONE_MIC)
        self._mic_dd_widget = ctk.CTkOptionMenu(
            r1,
            variable=self._mic_var,
            values=self._mic_items,
            fg_color=theme.PANEL,
            button_color=_P,
            button_hover_color=_PH,
            dropdown_fg_color=theme.ACCENT_DEEP,
            width=220,
        )
        self._mic_dd_widget.pack(side="right", padx=12, pady=8)

        r2 = ctk.CTkFrame(p, fg_color=_PD, corner_radius=8)
        r2.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(
            r2,
            text=i18n.t("audio.sys"),
            anchor="w",
            text_color=theme.TEXT_SOFT,
            font=ctk.CTkFont(size=12),
        ).pack(side="left", padx=(12, 0), pady=12)
        self._sys_var = ctk.StringVar(value=_NONE_SYS)
        self._sys_dd_widget = ctk.CTkOptionMenu(
            r2,
            variable=self._sys_var,
            values=self._sys_items,
            fg_color=theme.PANEL,
            button_color=_P,
            button_hover_color=_PH,
            dropdown_fg_color=theme.ACCENT_DEEP,
            width=220,
        )
        self._sys_dd_widget.pack(side="right", padx=12, pady=8)

        hint_row = ctk.CTkFrame(p, fg_color="transparent")
        hint_row.pack(fill="x", padx=14, pady=(2, 4))
        self._audio_hint = ctk.CTkLabel(
            hint_row,
            text=i18n.t("audio.loading"),
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_DIM,
        )
        self._audio_hint.pack(side="left", anchor="w")
        self._audio_refresh_btn = ctk.CTkButton(
            hint_row,
            text=i18n.t("audio.refresh"),
            width=72,
            fg_color=theme.PANEL,
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
            self._audio_hint.configure(text=i18n.t("audio.loading"), text_color=theme.TEXT_DIM)
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
                if n > 0:
                    self._audio_hint.configure(
                        text=i18n.t("audio.found", n=n),
                        text_color=theme.TEXT_DIM,
                    )
                else:
                    self._audio_hint.configure(
                        text=i18n.t("audio.limited"),
                        text_color=theme.WARNING,
                    )
        except Exception:
            pass

    def _sec(self, p, key):
        ctk.CTkLabel(
            p,
            text=i18n.t(key),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.ACCENT,
        ).pack(anchor="w", padx=12, pady=(20, 2))
        ctk.CTkFrame(p, height=1, fg_color=theme.SEPARATOR).pack(fill="x", padx=8, pady=(0, 6))

    def _sld(self, p, k, label_key, f, t, hint_key=None):
        v = ctk.IntVar(value=int(config.get(k)))
        self._v[k] = (v, int)
        r = ctk.CTkFrame(p, fg_color=_PD, corner_radius=8)
        r.pack(fill="x", padx=8, pady=4)
        top = ctk.CTkFrame(r, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 2))
        ctk.CTkLabel(
            top,
            text=i18n.t(label_key),
            anchor="w",
            text_color=theme.TEXT_SOFT,
            font=ctk.CTkFont(size=12),
        ).pack(side="left")
        lb = ctk.CTkLabel(
            top,
            text=str(v.get()),
            width=40,
            text_color="white",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        lb.pack(side="right")
        if hint_key:
            ctk.CTkLabel(
                r,
                text=i18n.t(hint_key),
                anchor="w",
                text_color=theme.VERSION_MUTED,
                font=ctk.CTkFont(size=10),
                wraplength=260,
            ).pack(fill="x", padx=12, pady=(0, 6))
        ctk.CTkSlider(
            r,
            variable=v,
            from_=f,
            to=t,
            number_of_steps=t - f,
            button_color=_P,
            button_hover_color=_PH,
            progress_color=_P,
            height=16,
            command=lambda x, lb=lb: lb.configure(text=str(int(float(x)))),
        ).pack(fill="x", padx=12, pady=(0, 12))

    def _tgl(self, p, k, label_key):
        v = ctk.BooleanVar(value=bool(config.get(k)))
        self._v[k] = (v, bool)
        r = ctk.CTkFrame(p, fg_color=_PD, corner_radius=8)
        r.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(
            r,
            text=i18n.t(label_key),
            anchor="w",
            text_color=theme.TEXT_SOFT,
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

    def _ent(self, p, k, label_key):
        v = ctk.StringVar(value=str(config.get(k)))
        self._v[k] = (v, str)
        r = ctk.CTkFrame(p, fg_color=_PD, corner_radius=8)
        r.pack(fill="x", padx=8, pady=4)
        ctk.CTkLabel(
            r,
            text=i18n.t(label_key),
            anchor="w",
            text_color=theme.TEXT_SOFT,
            font=ctk.CTkFont(size=12),
            wraplength=180,
        ).pack(side="left", padx=(12, 0), pady=12)
        ctk.CTkEntry(
            r, textvariable=v, width=110, border_color=_P, fg_color=theme.BG
        ).pack(side="right", padx=12, pady=8)

    def _fld(self, p, k):
        v = ctk.StringVar(value=str(config.get(k)))
        self._v[k] = (v, str)
        r = ctk.CTkFrame(p, fg_color=_PD, corner_radius=8)
        r.pack(fill="x", padx=8, pady=4)
        ctk.CTkEntry(
            r, textvariable=v, border_color=theme.SBG, fg_color=theme.BG
        ).pack(side="left", fill="x", expand=True, padx=(12, 6), pady=10)
        ctk.CTkButton(
            r,
            text=i18n.t("out.browse"),
            width=68,
            fg_color=theme.PANEL,
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
            text=i18n.t("su.on") if reg else i18n.t("su.off"),
            text_color=theme.GREEN if reg else theme.TEXT_DIM,
            anchor="w",
            font=ctk.CTkFont(size=12),
        )
        self._sl.pack(side="left", padx=(14, 0), pady=10)
        ctk.CTkButton(
            r,
            text=i18n.t("su.toggle"),
            width=90,
            fg_color=theme.BTN_DARK,
            hover_color=_PH,
            border_width=1,
            border_color=_P,
            command=self._ts,
        ).pack(side="right", padx=14)

    def _ts(self):
        if startup.is_registered():
            startup.unregister()
            self._sl.configure(text=i18n.t("su.off"), text_color=theme.TEXT_DIM)
        else:
            if startup.register():
                self._sl.configure(text=i18n.t("su.on"), text_color=theme.GREEN)

    def _save(self):
        mon_sel = self._mon_var.get()
        if mon_sel in self._mon_items:
            mon_idx = self._mon_items.index(mon_sel) + 1
        else:
            mon_idx = 1
        config.set("monitor_index", mon_idx)

        try:
            flabels = i18n.flip_labels()
            fi = flabels.index(self._flip_var.get())
            config.set("capture_flip", _FLIP_VALUES[fi])
        except (ValueError, AttributeError):
            config.set("capture_flip", "none")

        try:
            rlabels = i18n.res_cap_labels()
            ri = rlabels.index(self._res_cap_var.get())
            config.set("capture_max_height", _RES_CAP_VALUES[ri])
        except (ValueError, AttributeError):
            config.set("capture_max_height", 720)

        try:
            labels = i18n.encoder_labels()
            ei = labels.index(self._enc_var.get())
            config.set("video_encoder", _ENC_VALUES[ei])
        except ValueError:
            config.set("video_encoder", "auto")

        try:
            plabels = i18n.buffer_profile_labels()
            pi = plabels.index(self._profile_var.get())
            config.set("buffer_encoder_profile", _PROFILE_VALUES[pi])
        except (ValueError, AttributeError):
            config.set("buffer_encoder_profile", "balanced")

        try:
            blabels = i18n.capture_backend_labels()
            bi = blabels.index(self._backend_var.get())
            config.set("capture_backend", _BACKEND_VALUES[bi])
        except (ValueError, AttributeError):
            config.set("capture_backend", "ddagrab")

        try:
            glabels = i18n.game_mode_labels()
            gi = glabels.index(self._game_mode_var.get())
            config.set("game_mode", _GAME_MODE_VALUES[gi])
        except (ValueError, AttributeError):
            config.set("game_mode", "auto")

        from audio_devices import label_to_config

        config.set("mic_device", label_to_config(self._mic_var.get(), "mic"))
        config.set("sys_audio_device", label_to_config(self._sys_var.get(), "sys"))

        plabs = getattr(self, "_panel_labels", i18n.panel_side_labels())
        sel = self._side_var.get()
        config.set("panel_side", "left" if sel == plabs[0] else "right")

        try:
            if getattr(self, "_stats_corner_labels", None) and getattr(
                self, "_stats_corner_var", None
            ):
                ci = self._stats_corner_labels.index(self._stats_corner_var.get())
                config.set("stats_overlay_corner", self._stats_corner_codes[ci])
        except Exception:
            pass

        try:
            if getattr(self, "_ind_corner_labels", None) and getattr(
                self, "_ind_corner_var", None
            ):
                ii = self._ind_corner_labels.index(self._ind_corner_var.get())
                config.set("overlay_corner", self._ind_corner_codes[ii])
        except Exception:
            pass

        try:
            if getattr(self, "_stats_mode_labels", None) and getattr(
                self, "_stats_mode_var", None
            ):
                mi = self._stats_mode_labels.index(self._stats_mode_var.get())
                config.set("stats_overlay_mode", self._stats_mode_codes[mi])
        except Exception:
            pass

        for k, (v, c) in self._v.items():
            try:
                config.set(k, c(v.get()))
            except Exception:
                pass

        config.save()
        self.app.on_settings_saved()
