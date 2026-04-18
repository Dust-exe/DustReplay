import datetime
import os
import subprocess

import customtkinter as ctk

import config

_P = "#8833ee"
_PD = "#0e0018"


class RecordingsPage(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="transparent")
        self._rows = []
        self._build()

    def _build(self):
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=24, pady=(22, 10))
        ctk.CTkLabel(
            top,
            text="\U0001f3ac  Recordings",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="white",
        ).pack(side="left")
        ctk.CTkButton(
            top,
            text="Open folder",
            width=120,
            height=34,
            fg_color="#2a004a",
            hover_color="#3d1080",
            border_width=1,
            border_color=_P,
            command=lambda: (
                os.makedirs(config.get("output_dir"), exist_ok=True),
                subprocess.Popen(["explorer", config.get("output_dir")]),
            ),
        ).pack(side="right")
        ctk.CTkButton(
            top,
            text="\u21ba Refresh",
            width=85,
            height=34,
            fg_color="#1e003a",
            hover_color="#2a004a",
            command=self.refresh,
        ).pack(side="right", padx=(0, 8))
        self.scroll = ctk.CTkScrollableFrame(
            self, corner_radius=14, fg_color="#110020", scrollbar_button_color=_P
        )
        self.scroll.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.refresh()

    def refresh(self):
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
            r.pack(fill="x", pady=4)
            self._rows.append(r)

    def _empty(self):
        l = ctk.CTkLabel(
            self.scroll,
            text="\U0001f4c2  No recordings yet.",
            font=ctk.CTkFont(size=14),
            text_color="#554477",
        )
        l.pack(pady=50)
        self._rows.append(l)

    def _mkrow(self, fp, fn):
        r = ctk.CTkFrame(
            self.scroll,
            corner_radius=12,
            height=60,
            fg_color=_PD,
            border_width=1,
            border_color="#3d1080",
        )
        r.pack_propagate(False)
        ctk.CTkLabel(
            r,
            text=fn,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="white",
            anchor="w",
        ).place(x=14, y=9)
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
            text_color="#aa77ff",
            anchor="w",
        ).place(x=14, y=34)
        ctk.CTkButton(
            r,
            text="Delete",
            width=52,
            height=30,
            fg_color="#5a1a1a",
            hover_color="#8a2020",
            corner_radius=8,
            command=lambda: (os.remove(fp), self.refresh()) if os.path.isfile(fp) else None,
        ).place(relx=1.0, rely=0.5, anchor="e", x=-10)
        ctk.CTkButton(
            r,
            text="Play",
            width=60,
            height=30,
            fg_color="#2a004a",
            hover_color="#3d1080",
            corner_radius=8,
            border_width=1,
            border_color=_P,
            command=lambda: os.startfile(fp),
        ).place(relx=1.0, rely=0.5, anchor="e", x=-72)
        return r
