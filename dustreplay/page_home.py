import datetime
import glob
import os
import subprocess
import threading
import tkinter as tk

import customtkinter as ctk
from PIL import Image

import config
import i18n

_BG = "#050508"
_HV = "#0d0d1a"
_CAR = "#0d0d1a"
_SEP = "#1c1c2e"
_P = "#8833ee"
_WH = "#ffffff"
_GR = "#888899"
_RED = "#e03030"


class HomePage(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=_BG)
        self.app = app
        self._tcache = {}
        self._ticon_lbl = None
        self._ttitle_lbl = None
        self._sub_save = None
        self._sub_stop = None
        self._manual_icon = None
        self._manual_title = None
        self._sub_manual = None
        self._build()
        self._load_gallery()

    def _sep(self):
        ctk.CTkFrame(self, height=1, fg_color=_SEP).pack(fill="x")

    def _sec_hdr(self, icon, title, right_txt=None, right_cmd=None):
        f = ctk.CTkFrame(self, fg_color="transparent", height=40)
        f.pack(fill="x")
        f.pack_propagate(False)
        inn = ctk.CTkFrame(f, fg_color="transparent")
        inn.place(relx=0, rely=0, relwidth=1, relheight=1)
        ctk.CTkLabel(
            inn, text=icon, font=ctk.CTkFont(size=16), width=44, text_color=_WH
        ).pack(side="left", padx=(12, 2))
        ctk.CTkLabel(
            inn,
            text=title,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=_WH,
            anchor="w",
        ).pack(side="left", fill="y")
        if right_txt:
            ctk.CTkButton(
                inn,
                text=right_txt,
                width=54,
                height=22,
                font=ctk.CTkFont(size=10),
                fg_color="transparent",
                hover_color=_HV,
                text_color=_GR,
                command=right_cmd or (lambda: None),
            ).pack(side="right", padx=10)

    def _build(self):
        self._build_gallery()
        self._sep()
        self._build_actions()
        self._sep()
        self._build_audio()
        self._sep()
        self._build_stats()

    def _build_gallery(self):
        f = ctk.CTkFrame(self, fg_color="transparent", height=40)
        f.pack(fill="x")
        f.pack_propagate(False)
        inn = ctk.CTkFrame(f, fg_color="transparent")
        inn.place(relx=0, rely=0, relwidth=1, relheight=1)
        ctk.CTkLabel(
            inn, text="\U0001f3ac", font=ctk.CTkFont(size=16), width=44, text_color=_WH
        ).pack(side="left", padx=(12, 2))
        self._gal_title_lbl = ctk.CTkLabel(
            inn,
            text=i18n.t("home.gallery"),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=_WH,
            anchor="w",
        )
        self._gal_title_lbl.pack(side="left", fill="y")
        self._gal_all_btn = ctk.CTkButton(
            inn,
            text=i18n.t("home.gallery_all"),
            width=54,
            height=22,
            font=ctk.CTkFont(size=10),
            fg_color="transparent",
            hover_color=_HV,
            text_color=_GR,
            command=lambda: self.app.sp("recordings"),
        )
        self._gal_all_btn.pack(side="right", padx=10)
        self._gcanvas = tk.Canvas(self, bg=_BG, highlightthickness=0, height=104)
        self._gcanvas.pack(fill="x", padx=8, pady=(0, 8))
        self._gframe = tk.Frame(self._gcanvas, bg=_BG)
        self._gcanvas.create_window(0, 0, anchor="nw", window=self._gframe)
        self._gcanvas.bind(
            "<MouseWheel>",
            lambda e: self._gcanvas.xview_scroll(int(-e.delta / 60), "units"),
        )
        self._gempty = ctk.CTkLabel(
            self,
            text=i18n.t("home.gallery_empty"),
            font=ctk.CTkFont(size=11),
            text_color=_GR,
        )

    def _load_gallery(self):
        def _w():
            od = config.get("output_dir")
            files = []
            if os.path.isdir(od):
                rep = glob.glob(os.path.join(od, "replay_*.mp4"))
                man = glob.glob(os.path.join(od, "manual_*.mp4"))
                files = sorted(rep + man, key=os.path.getmtime, reverse=True)[:8]
            self.after(0, lambda f=files: self._show_gallery(f))

        threading.Thread(target=_w, daemon=True).start()

    def _show_gallery(self, files):
        for w in self._gframe.winfo_children():
            w.destroy()
        if not files:
            self._gcanvas.pack_forget()
            self._gempty.pack(pady=10)
            return
        self._gempty.pack_forget()
        if not self._gcanvas.winfo_ismapped():
            self._gcanvas.pack(fill="x", padx=8, pady=(0, 8))
        for fp in files:
            self._add_thumb(fp)
        self._gframe.update_idletasks()
        self._gcanvas.configure(scrollregion=self._gcanvas.bbox("all"))

    def _add_thumb(self, fp):
        fn = os.path.basename(fp)
        try:
            dt = datetime.datetime.strptime(fn, "replay_%Y-%m-%d_%H-%M-%S.mp4")
            lbl = dt.strftime("%d.%m  %H:%M")
        except Exception:
            lbl = fn[:13]
        try:
            sz = os.path.getsize(fp)
            ds = max(0, int(sz / (600 * 1024)))
            dur = f"{ds // 60}:{ds % 60:02d}"
        except Exception:
            dur = "--:--"

        card = tk.Frame(self._gframe, bg=_CAR, cursor="hand2")
        card.pack(side="left", padx=3, pady=2)

        tv = tk.Frame(card, bg="#111122", width=104, height=65)
        tv.pack(padx=2, pady=(2, 0))
        tv.pack_propagate(False)
        pl = tk.Label(tv, text="\u25b6", font=("Segoe UI", 18), fg="#2a2a4a", bg="#111122")
        pl.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(
            tv,
            text=dur,
            font=("Segoe UI", 7, "bold"),
            fg="white",
            bg="#000000",
        ).place(relx=1.0, rely=1.0, anchor="se", x=-2, y=-1)

        dk = tk.Label(card, text=lbl, font=("Segoe UI", 8), fg=_GR, bg=_CAR)
        dk.pack(pady=(2, 4))

        def _open(p=fp):
            try:
                if hasattr(self.app, "close_panel"):
                    self.app.close_panel()
                os.startfile(os.path.normpath(p))
            except Exception:
                pass

        for w in (card, tv, pl, dk):
            w.bind("<Button-1>", lambda e, p=fp: _open())
        self._gen_thumb(fp, tv, pl, _open)

    def _gen_thumb(self, fp, parent, placeholder, open_cmd):
        if fp in self._tcache:
            self._set_thumb(parent, self._tcache[fp], placeholder, open_cmd)
            return
        ff = os.path.join(config.APPDATA_DIR, "ffmpeg", "ffmpeg.exe")
        if not os.path.isfile(ff):
            return
        td = os.path.join(config.APPDATA_DIR, "thumbs")
        os.makedirs(td, exist_ok=True)
        tp = os.path.join(td, os.path.basename(fp) + ".jpg")

        def _w():
            try:
                if not os.path.isfile(tp):
                    subprocess.run(
                        [
                            ff,
                            "-y",
                            "-ss",
                            "5",
                            "-i",
                            fp,
                            "-vframes",
                            "1",
                            "-s",
                            "104x65",
                            "-q:v",
                            "4",
                            tp,
                        ],
                        capture_output=True,
                        timeout=10,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )
                if os.path.isfile(tp):
                    img = Image.open(tp)
                    rsmp = getattr(Image, "LANCZOS", getattr(Image, "ANTIALIAS", None))
                    img = img.resize((104, 65), rsmp) if rsmp else img.resize((104, 65))
                    ci = ctk.CTkImage(light_image=img, dark_image=img, size=(104, 65))
                    self._tcache[fp] = ci
                    self.after(0, lambda: self._set_thumb(parent, ci, placeholder, open_cmd))
            except Exception:
                pass

        threading.Thread(target=_w, daemon=True).start()

    def _set_thumb(self, parent, img, placeholder=None, open_cmd=None):
        try:
            if placeholder:
                placeholder.place_forget()
            lbl = ctk.CTkLabel(parent, image=img, text="", cursor="hand2")
            lbl.place(relx=0.5, rely=0.5, anchor="center")
            if open_cmd:
                lbl.bind("<Button-1>", lambda e: open_cmd())
        except Exception:
            pass

    def _build_actions(self):
        hk_s = str(config.get("hotkey_save")).upper()
        hk_t = str(config.get("hotkey_toggle")).upper()
        _, self._title_save, self._sub_save = self._action_row(
            "\U0001f4be",
            i18n.t("home.save"),
            i18n.t("home.hotkey", hk=hk_s),
            self.app.do_save,
        )
        self._manual_icon, self._manual_title, self._sub_manual = self._action_row(
            "\U0001f3a5",
            i18n.t("home.direct"),
            i18n.t("home.direct_sub"),
            self._on_manual_row_click,
        )
        self._ticon_lbl, self._ttitle_lbl, self._sub_stop = self._action_row(
            "\u23f8",
            i18n.t("home.cap_stop"),
            i18n.t("home.hotkey", hk=hk_t),
            self.app.do_toggle,
        )
        _, self._title_rec, self._sub_rec = self._action_row(
            "\U0001f3ac",
            i18n.t("home.recordings"),
            i18n.t("home.recordings_sub"),
            lambda: self.app.sp("recordings"),
        )
        _, self._title_set, self._sub_set = self._action_row(
            "\u2699",
            i18n.t("home.settings"),
            i18n.t("home.settings_sub"),
            lambda: self.app.sp("settings"),
        )

    def _action_row(self, icon, title, sub="", cmd=None):
        row = ctk.CTkFrame(self, fg_color="transparent", height=54, cursor="hand2")
        row.pack(fill="x")
        row.pack_propagate(False)
        row.bind("<Enter>", lambda e: row.configure(fg_color=_HV))
        row.bind("<Leave>", lambda e: row.configure(fg_color="transparent"))

        inn = ctk.CTkFrame(row, fg_color="transparent")
        inn.place(relx=0, rely=0, relwidth=1, relheight=1)
        inn.bind("<Enter>", lambda e: row.configure(fg_color=_HV))
        inn.bind("<Leave>", lambda e: row.configure(fg_color="transparent"))

        il = ctk.CTkLabel(
            inn, text=icon, font=ctk.CTkFont(size=17), width=46, text_color=_WH
        )
        il.pack(side="left", padx=(8, 0))
        tf = ctk.CTkFrame(inn, fg_color="transparent")
        tf.pack(side="left", fill="both", expand=True, pady=8)
        tl = ctk.CTkLabel(
            tf, text=title, font=ctk.CTkFont(size=13, weight="bold"), text_color=_WH, anchor="w"
        )
        tl.pack(fill="x")
        sl = ctk.CTkLabel(
            tf, text=sub, font=ctk.CTkFont(size=10), text_color=_GR, anchor="w"
        )
        sl.pack(fill="x")
        al = ctk.CTkLabel(inn, text="\u203a", font=ctk.CTkFont(size=22), text_color=_GR, width=30)
        al.pack(side="right", padx=8)

        if cmd:
            for w in (row, inn, il, tf, tl, sl, al):
                try:
                    w.bind("<Button-1>", lambda e, c=cmd: c())
                except Exception:
                    pass
            for w in (il, tf, tl, sl, al):
                try:
                    w.bind("<Enter>", lambda e: row.configure(fg_color=_HV))
                    w.bind("<Leave>", lambda e: row.configure(fg_color="transparent"))
                except Exception:
                    pass
        return il, tl, sl

    def _build_audio(self):
        mic = config.get("mic_device") or "(none)"
        if "voicemeeter" in mic.lower():
            mic = mic.split("(")[0].strip()
        mic = (mic[:30] + "\u2026") if len(mic) > 30 else mic
        sys_d = config.get("sys_audio_device") or "(none)"
        if sys_d == "__wasapi_out__":
            sys_d = "Windows default loopback"
        elif "voicemeeter" in sys_d.lower():
            sys_d = sys_d.split("(")[0].strip()
        sys_d = (sys_d[:30] + "\u2026") if len(sys_d) > 30 else sys_d
        self._info_row("\U0001f3a7", "Microphone", mic)
        self._info_row("\U0001f50a", "System audio", sys_d)

    def _info_row(self, icon, title, val):
        row = ctk.CTkFrame(self, fg_color="transparent", height=48)
        row.pack(fill="x")
        row.pack_propagate(False)
        inn = ctk.CTkFrame(row, fg_color="transparent")
        inn.place(relx=0, rely=0, relwidth=1, relheight=1)
        ctk.CTkLabel(
            inn, text=icon, font=ctk.CTkFont(size=16), width=46, text_color=_WH
        ).pack(side="left", padx=(8, 0))
        tf = ctk.CTkFrame(inn, fg_color="transparent")
        tf.pack(side="left", fill="both", expand=True, pady=6)
        ctk.CTkLabel(
            tf, text=title, font=ctk.CTkFont(size=12, weight="bold"), text_color=_WH, anchor="w"
        ).pack(fill="x")
        ctk.CTkLabel(tf, text=val, font=ctk.CTkFont(size=10), text_color=_GR, anchor="w").pack(
            fill="x"
        )

    def _on_manual_row_click(self):
        self.app.toggle_manual_recording()

    def _open_stats(self):
        self.app.open_stats_window()

    def _build_stats(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent", height=40, cursor="hand2")
        hdr.pack(fill="x")
        hdr.bind("<Enter>", lambda e: hdr.configure(fg_color=_HV))
        hdr.bind("<Leave>", lambda e: hdr.configure(fg_color="transparent"))
        inn = ctk.CTkFrame(hdr, fg_color="transparent")
        inn.place(relx=0, rely=0, relwidth=1, relheight=1)
        for w in (hdr, inn):
            w.bind("<Button-1>", lambda e: self._open_stats())
        ctk.CTkLabel(
            inn, text="\U0001f4ca", font=ctk.CTkFont(size=16), width=44, text_color=_WH
        ).pack(side="left", padx=(12, 2))
        ctk.CTkLabel(
            inn,
            text=i18n.t("home.stats_title"),
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=_WH,
            anchor="w",
        ).pack(side="left", fill="y")
        ctk.CTkLabel(
            inn,
            text=i18n.t("home.stats_hint"),
            font=ctk.CTkFont(size=10),
            text_color=_GR,
        ).pack(side="right", padx=12)
        for w in inn.winfo_children():
            w.bind("<Enter>", lambda e: hdr.configure(fg_color=_HV))
            w.bind("<Leave>", lambda e: hdr.configure(fg_color="transparent"))
            w.bind("<Button-1>", lambda e: self._open_stats())

        sf = ctk.CTkFrame(self, fg_color=_CAR, corner_radius=8, cursor="hand2")
        sf.pack(fill="x", padx=10, pady=(0, 10))
        sf.bind("<Button-1>", lambda e: self._open_stats())

        br = ctk.CTkFrame(sf, fg_color="transparent")
        br.pack(fill="x", padx=12, pady=(10, 2))
        br.bind("<Button-1>", lambda e: self._open_stats())
        ctk.CTkLabel(br, text="Buffer", font=ctk.CTkFont(size=11), text_color=_GR).pack(
            side="left"
        )
        self.bl = ctk.CTkLabel(
            br,
            text="0:00 / 5:00",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=_WH,
        )
        self.bl.pack(side="right")
        for w in br.winfo_children():
            w.bind("<Button-1>", lambda e: self._open_stats())

        self.pb = ctk.CTkProgressBar(
            sf, height=5, progress_color=_P, fg_color="#1a1a2e", corner_radius=3
        )
        self.pb.pack(fill="x", padx=12, pady=(0, 2))
        self.pb.set(0)
        self.pb.bind("<Button-1>", lambda e: self._open_stats())

        fr = ctk.CTkFrame(sf, fg_color="transparent")
        fr.pack(fill="x", padx=12, pady=(4, 10))
        fr.bind("<Button-1>", lambda e: self._open_stats())
        fps = str(config.get("fps"))
        mon = int(config.get("monitor_index") or 1)
        self._stat_lbl = ctk.CTkLabel(
            fr,
            text=i18n.t("home.stat_line", fps=fps, mon=mon),
            font=ctk.CTkFont(size=10),
            text_color=_GR,
        )
        self._stat_lbl.pack(side="left")
        for w in fr.winfo_children():
            w.bind("<Button-1>", lambda e: self._open_stats())

        self.il = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=11))
        self.il.pack(pady=(0, 8))

    def set_manual_ui(self, active: bool):
        if not self._manual_title:
            return
        if active:
            self._manual_icon.configure(text="\u23f9")
            self._manual_title.configure(text=i18n.t("home.direct_stop"))
            self._sub_manual.configure(text=i18n.t("home.direct_stop_sub"))
        else:
            self._manual_icon.configure(text="\U0001f3a5")
            self._manual_title.configure(text=i18n.t("home.direct"))
            self._sub_manual.configure(text=i18n.t("home.direct_sub"))

    def set_recording(self, rec):
        try:
            if rec:
                self._ticon_lbl.configure(text="\u23f8")
                self._ttitle_lbl.configure(text=i18n.t("home.cap_stop"))
            else:
                self._ticon_lbl.configure(text="\u25b6")
                self._ttitle_lbl.configure(text=i18n.t("home.cap_start"))
        except Exception:
            pass

    def update_buffer(self, fs):
        ts = config.get("buffer_minutes") * 60
        fs = min(fs, ts)
        self.pb.set(fs / ts if ts else 0)
        m, s = divmod(int(fs), 60)
        tm, tss = divmod(int(ts), 60)
        self.bl.configure(text=f"{m}:{s:02d} / {tm}:{tss:02d}")

    def show_info(self, msg, color="#4caf50"):
        self.il.configure(text=msg, text_color=color)
        self.after(5000, lambda: self.il.configure(text=""))

    def refresh_hotkeys(self):
        if self._sub_save:
            self._sub_save.configure(
                text=i18n.t("home.hotkey", hk=str(config.get("hotkey_save")).upper())
            )
        if self._sub_stop:
            self._sub_stop.configure(
                text=i18n.t("home.hotkey", hk=str(config.get("hotkey_toggle")).upper())
            )
        try:
            mon = int(config.get("monitor_index") or 1)
            fps = str(config.get("fps"))
            self._stat_lbl.configure(text=i18n.t("home.stat_line", fps=fps, mon=mon))
        except Exception:
            pass

    def refresh_home_texts(self):
        """Re-apply labels when UI language changes."""
        hk_s = str(config.get("hotkey_save")).upper()
        hk_t = str(config.get("hotkey_toggle")).upper()
        if getattr(self, "_gal_title_lbl", None):
            self._gal_title_lbl.configure(text=i18n.t("home.gallery"))
        if getattr(self, "_gal_all_btn", None):
            self._gal_all_btn.configure(text=i18n.t("home.gallery_all"))
        if getattr(self, "_gempty", None):
            self._gempty.configure(text=i18n.t("home.gallery_empty"))
        if getattr(self, "_title_save", None):
            self._title_save.configure(text=i18n.t("home.save"))
        if self._sub_save:
            self._sub_save.configure(text=i18n.t("home.hotkey", hk=hk_s))
        if getattr(self, "_manual_title", None) and self._sub_manual:
            if self.app.recorder.manual_recording_active():
                self._manual_title.configure(text=i18n.t("home.direct_stop"))
                self._sub_manual.configure(text=i18n.t("home.direct_stop_sub"))
            else:
                self._manual_title.configure(text=i18n.t("home.direct"))
                self._sub_manual.configure(text=i18n.t("home.direct_sub"))
        if self._sub_stop:
            self._sub_stop.configure(text=i18n.t("home.hotkey", hk=hk_t))
        if getattr(self, "_title_rec", None):
            self._title_rec.configure(text=i18n.t("home.recordings"))
        if getattr(self, "_sub_rec", None):
            self._sub_rec.configure(text=i18n.t("home.recordings_sub"))
        if getattr(self, "_title_set", None):
            self._title_set.configure(text=i18n.t("home.settings"))
        if getattr(self, "_sub_set", None):
            self._sub_set.configure(text=i18n.t("home.settings_sub"))
        if self._ttitle_lbl:
            self.set_recording(getattr(self.app, "_recording", True))
        self.refresh_hotkeys()

    def refresh_gallery(self):
        self._load_gallery()
