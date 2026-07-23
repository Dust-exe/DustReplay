import datetime
import os
import subprocess

import customtkinter as ctk
from PIL import Image

import config
import i18n
import theme
import thumb_cache
from clip_editor import ClipEditor
from gif_maker import GifMakerDialog

_P = theme.P
_PD = theme.PD


class RecordingsPage(ctk.CTkFrame):
    def __init__(self, master, app=None):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._rows = []
        self._top_open = None
        self._top_refresh = None
        self._build()

    def refresh_ui_texts(self):
        if self._top_open:
            self._top_open.configure(text=i18n.t("rec.open_folder"))
        if self._top_refresh:
            self._top_refresh.configure(text=i18n.t("rec.refresh"))
        if hasattr(self, "_title_lbl"):
            self._title_lbl.configure(text=i18n.t("rec.page_title"))

    def _build(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=24, pady=(22, 10))
        self._title_lbl = ctk.CTkLabel(
            top,
            text=i18n.t("rec.page_title"),
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=theme.TEXT,
        )
        self._title_lbl.pack(side="left")
        self._top_open = ctk.CTkButton(
            top,
            text=i18n.t("rec.open_folder"),
            width=120,
            height=34,
            fg_color=theme.BTN_DARK,
            hover_color=theme.ACCENT_HOVER,
            border_width=1,
            border_color=_P,
            command=self._open_folder,
        )
        self._top_open.pack(side="right")
        self._top_refresh = ctk.CTkButton(
            top,
            text=i18n.t("rec.refresh"),
            width=85,
            height=34,
            fg_color=theme.ACCENT_DEEP,
            hover_color=theme.BTN_DARK,
            command=self.refresh,
        )
        self._top_refresh.pack(side="right", padx=(0, 8))
        self.scroll = ctk.CTkScrollableFrame(
            self,
            corner_radius=14,
            fg_color=theme.BACKDROP,
            scrollbar_button_color=_P,
        )
        self.scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.refresh()

    def refresh(self):
        self.refresh_ui_texts()
        for w in self._rows:
            w.destroy()
        self._rows.clear()
        od = config.get("output_dir")
        if not os.path.isdir(od):
            self._empty()
            return
        files = sorted(
            [f for f in os.listdir(od) if f.lower().endswith(".mp4")],
            key=lambda f: os.path.getmtime(os.path.join(od, f)),
            reverse=True,
        )
        if not files:
            self._empty()
            return
        for fn in files:
            fp = os.path.join(od, fn)
            r = self._mkrow(fp, fn)
            r.pack(fill="x", pady=6)
            self._rows.append(r)

    def _empty(self):
        l = ctk.CTkLabel(
            self.scroll,
            text=i18n.t("rec.empty"),
            font=ctk.CTkFont(size=14),
            text_color=theme.TEXT_DIM,
        )
        l.pack(pady=50)
        self._rows.append(l)

    def _set_thumb(self, lbl: ctk.CTkLabel, path: str) -> None:
        try:
            pil = Image.open(path).convert("RGBA")
            pil.thumbnail((118, 66), Image.Resampling.LANCZOS)
            img = ctk.CTkImage(
                light_image=pil, dark_image=pil, size=(pil.width, pil.height)
            )
            lbl.configure(image=img, text="")
            lbl._dr_img = img
        except Exception:
            pass

    def _mkrow(self, fp, fn):
        r = ctk.CTkFrame(
            self.scroll,
            corner_radius=12,
            height=96,
            fg_color=_PD,
            border_width=1,
            border_color=theme.ACCENT_HOVER,
        )
        r.pack_propagate(False)

        thumb_wrap = ctk.CTkFrame(
            r, width=124, height=72, fg_color=theme.BACKDROP, corner_radius=8
        )
        thumb_wrap.place(x=10, y=12)
        thumb_wrap.pack_propagate(False)
        ph = ctk.CTkLabel(
            thumb_wrap,
            text="MP4",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme.TEXT_DIM,
            width=118,
            height=66,
        )
        ph.place(relx=0.5, rely=0.5, anchor="center")

        thumb_cache.ensure_thumb_jpeg(fp, self, lambda p, L=ph: self._set_thumb(L, p))

        ctk.CTkLabel(
            r,
            text=fn,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=theme.TEXT,
            anchor="w",
        ).place(x=146, y=14)
        try:
            sz = f"{os.path.getsize(fp) / 1048576:.1f} MB"
            dt = datetime.datetime.fromtimestamp(os.path.getmtime(fp)).strftime(
                "%Y-%m-%d %H:%M"
            )
        except Exception:
            sz, dt = "-", "-"
        ctk.CTkLabel(
            r,
            text=f"\U0001f552 {dt}   \U0001f4be {sz}",
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_SOFT,
            anchor="w",
        ).place(x=146, y=44)
        ctk.CTkButton(
            r,
            text=i18n.t("rec.delete"),
            width=52,
            height=30,
            fg_color=theme.RED,
            hover_color="#8a3030",
            corner_radius=8,
            command=lambda: (os.remove(fp), self.refresh()) if os.path.isfile(fp) else None,
        ).place(relx=1.0, rely=0.5, anchor="e", x=-10)
        ctk.CTkButton(
            r,
            text=i18n.t("rec.play"),
            width=60,
            height=30,
            fg_color=theme.BTN_DARK,
            hover_color=theme.ACCENT_HOVER,
            corner_radius=8,
            border_width=1,
            border_color=_P,
            command=lambda: self._play_file(fp),
        ).place(relx=1.0, rely=0.5, anchor="e", x=-72)
        ctk.CTkButton(
            r,
            text="🎞️ GIF",
            width=60,
            height=30,
            fg_color=theme.BTN_DARK,
            hover_color=theme.ACCENT_HOVER,
            corner_radius=8,
            command=lambda: GifMakerDialog(self, fp, self.refresh),
        ).place(relx=1.0, rely=0.5, anchor="e", x=-142)
        ctk.CTkButton(
            r,
            text="✂️ Trim",
            width=60,
            height=30,
            fg_color=theme.BTN_DARK,
            hover_color=theme.ACCENT_HOVER,
            corner_radius=8,
            command=lambda: ClipEditor(self, fp, self.refresh),
        ).place(relx=1.0, rely=0.5, anchor="e", x=-212)
        return r

    def _open_folder(self):
        if self.app and hasattr(self.app, "close_panel"):
            self.app.close_panel()
        os.makedirs(config.get("output_dir"), exist_ok=True)
        subprocess.Popen(["explorer", config.get("output_dir")])

    def _play_file(self, fp):
        if self.app and hasattr(self.app, "close_panel"):
            self.app.close_panel()
        os.startfile(fp)
