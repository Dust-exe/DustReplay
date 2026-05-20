"""DustReplay main application window — wide view opened from tray icon."""
from __future__ import annotations

import datetime
import os

import customtkinter as ctk
from PIL import Image, ImageDraw

import branding_paths
import config
import i18n
import theme
import thumb_cache

_SIDEBAR_W = 190
_P = theme.P
_PH = theme.PH
_THUMB_W = 280
_THUMB_H = 158
_CARD_BG = (14, 10, 22)


def _placeholder_img() -> ctk.CTkImage:
    """Dark background with centered white play-circle."""
    img = Image.new("RGBA", (_THUMB_W, _THUMB_H), (*_CARD_BG, 255))
    d = ImageDraw.Draw(img)
    cx, cy, r = _THUMB_W // 2, _THUMB_H // 2, 30
    accent = (139, 108, 240, 230)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=accent)
    tx = cx - 9
    d.polygon([(tx, cy - 15), (tx, cy + 15), (cx + 19, cy)], fill=(*_CARD_BG, 255))
    return ctk.CTkImage(light_image=img.convert("RGB"), dark_image=img.convert("RGB"),
                        size=(_THUMB_W, _THUMB_H))


def _thumb_with_play(pil: Image.Image) -> ctk.CTkImage:
    """Blend frame at 50 % opacity and overlay play circle."""
    pil = pil.convert("RGB").resize((_THUMB_W, _THUMB_H), Image.Resampling.LANCZOS)
    bg = Image.new("RGB", pil.size, _CARD_BG)
    blended = Image.blend(pil, bg, alpha=0.5)
    d = ImageDraw.Draw(blended)
    cx, cy, r = _THUMB_W // 2, _THUMB_H // 2, 30
    accent = (139, 108, 240, 230)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=accent)
    tx = cx - 9
    d.polygon([(tx, cy - 15), (tx, cy + 15), (cx + 19, cy)], fill=_CARD_BG)
    return ctk.CTkImage(light_image=blended, dark_image=blended, size=(_THUMB_W, _THUMB_H))


class _GalleryPage(ctk.CTkFrame):
    """3-column thumbnail grid of recent recordings."""

    _COLS = 3

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._cards: list = []
        self._build()

    def _build(self):
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.pack(fill="x", padx=24, pady=(18, 10))
        ctk.CTkLabel(
            hdr,
            text=i18n.t("home.gallery"),
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=theme.TEXT,
        ).pack(side="left")
        ctk.CTkButton(
            hdr,
            text=i18n.t("rec.open_folder"),
            width=120,
            height=32,
            fg_color=theme.ACCENT_DEEP,
            hover_color=_PH,
            corner_radius=8,
            command=self._open_folder,
        ).pack(side="right", padx=(0, 0))
        ctk.CTkButton(
            hdr,
            text=i18n.t("rec.refresh"),
            width=90,
            height=32,
            fg_color=theme.BTN_DARK,
            hover_color=_PH,
            border_width=1,
            border_color=_P,
            corner_radius=8,
            command=self.refresh,
        ).pack(side="right", padx=(0, 8))

        self._scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=theme.BACKDROP,
            corner_radius=12,
            scrollbar_button_color=_P,
        )
        self._scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        for c in range(self._COLS):
            self._scroll.columnconfigure(c, weight=1)

        self.refresh()

    def _set_thumb(self, card: ctk.CTkFrame, path: str):
        try:
            pil = Image.open(path)
            img = _thumb_with_play(pil)
            lbl = card._thumb_lbl
            lbl.configure(image=img, text="")
            lbl._img = img
        except Exception:
            pass

    def refresh(self):
        for w in self._cards:
            try:
                w.destroy()
            except Exception:
                pass
        self._cards.clear()

        od = config.get("output_dir")
        if not os.path.isdir(od):
            self._empty()
            return

        files = sorted(
            [f for f in os.listdir(od) if f.lower().endswith(".mp4")],
            key=lambda f: os.path.getmtime(os.path.join(od, f)),
            reverse=True,
        )[:24]

        if not files:
            self._empty()
            return

        for idx, fn in enumerate(files):
            fp = os.path.join(od, fn)
            row, col = divmod(idx, self._COLS)
            card = self._mkcard(fp, fn)
            card.grid(row=row, column=col, padx=8, pady=8, sticky="nsew")
            self._cards.append(card)

    def _empty(self):
        lbl = ctk.CTkLabel(
            self._scroll,
            text=i18n.t("home.gallery_empty"),
            font=ctk.CTkFont(size=14),
            text_color=theme.TEXT_DIM,
        )
        lbl.grid(row=0, column=0, columnspan=self._COLS, pady=50)
        self._cards.append(lbl)

    def _mkcard(self, fp: str, fn: str) -> ctk.CTkFrame:
        card = ctk.CTkFrame(
            self._scroll,
            fg_color=theme.PD,
            corner_radius=12,
            border_width=1,
            border_color=theme.ACCENT_DEEP,
        )
        _ph = _placeholder_img()
        thumb_lbl = ctk.CTkLabel(
            card,
            image=_ph,
            text="",
            fg_color="transparent",
            width=_THUMB_W,
            height=_THUMB_H,
            corner_radius=8,
        )
        thumb_lbl._img = _ph
        thumb_lbl.pack(padx=8, pady=(8, 4), fill="x")
        card._thumb_lbl = thumb_lbl

        thumb_cache.ensure_thumb_jpeg(fp, self, lambda p, c=card: self._set_thumb(c, p))

        ctk.CTkLabel(
            card,
            text=fn,
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=theme.TEXT,
            anchor="w",
            wraplength=250,
        ).pack(padx=10, pady=(4, 0), fill="x")

        try:
            sz = f"{os.path.getsize(fp) / 1048576:.1f} MB"
            dt = datetime.datetime.fromtimestamp(os.path.getmtime(fp)).strftime(
                "%Y-%m-%d %H:%M"
            )
            info_text = f"{dt}  •  {sz}"
        except Exception:
            info_text = ""

        if info_text:
            ctk.CTkLabel(
                card,
                text=info_text,
                font=ctk.CTkFont(size=10),
                text_color=theme.TEXT_DIM,
                anchor="w",
            ).pack(padx=10, pady=(2, 4), fill="x")

        btns = ctk.CTkFrame(card, fg_color="transparent")
        btns.pack(fill="x", padx=8, pady=(4, 8))
        ctk.CTkButton(
            btns,
            text=i18n.t("rec.play"),
            height=28,
            fg_color=theme.BTN_DARK,
            hover_color=theme.ACCENT_HOVER,
            border_width=1,
            border_color=_P,
            corner_radius=8,
            command=lambda: os.startfile(fp),
        ).pack(side="left", padx=(0, 4))
        ctk.CTkButton(
            btns,
            text=i18n.t("rec.delete"),
            height=28,
            width=60,
            fg_color=theme.RED,
            hover_color="#8a3030",
            corner_radius=8,
            command=lambda: self._delete(fp),
        ).pack(side="right")
        return card

    def _delete(self, fp: str):
        try:
            if os.path.isfile(fp):
                os.remove(fp)
        except Exception:
            pass
        self.refresh()

    def _open_folder(self):
        import subprocess
        od = config.get("output_dir")
        os.makedirs(od, exist_ok=True)
        subprocess.Popen(["explorer", od])


def _resolve_logo_path() -> str | None:
    """User logo + bundled branding/logo.png."""
    candidates = [
        branding_paths.logo_png_path(),
        os.path.join(
            os.path.expanduser("~"),
            "Desktop",
            "dasasd",
            "dust logo.png",
        ),
        r"C:\Users\kaan3\Desktop\dasasd\dust logo.png",
    ]
    for p in candidates:
        if p and os.path.isfile(p):
            return p
    return None


def _load_logo_ctk(size: int = 22) -> ctk.CTkImage | None:
    lp = _resolve_logo_path()
    if not lp:
        return None
    try:
        pil = Image.open(lp).convert("RGBA")
        pil.thumbnail((size, size), Image.Resampling.LANCZOS)
        return ctk.CTkImage(light_image=pil, dark_image=pil, size=(size, size))
    except Exception:
        return None


class MainWindow(ctk.CTkToplevel):
    """Wide application window — WhatsApp-style merged title bar + sidebar."""

    _TITLE_H = 40

    def __init__(self, app):
        super().__init__()
        self.app = app
        self._pages: dict[str, ctk.CTkFrame] = {}
        self._nb: dict[str, ctk.CTkButton] = {}
        self._drag_x = 0
        self._drag_y = 0
        self._rs_x = self._rs_y = self._rs_w = self._rs_h = 0

        self.title(config.APP_DISPLAY)
        self.geometry("980x660")
        self.minsize(800, 520)
        self.configure(fg_color=theme.BG)
        self.protocol("WM_DELETE_WINDOW", self.hide)
        self.overrideredirect(True)

        self._build()
        self.withdraw()

    def _build_title_bar(self, parent):
        """Full-width top bar merged with window (no separate OS purple strip)."""
        bar = ctk.CTkFrame(parent, fg_color=theme.BG, corner_radius=0, height=self._TITLE_H)
        bar.pack(fill="x")
        bar.pack_propagate(False)

        left = ctk.CTkFrame(bar, fg_color="transparent")
        left.pack(side="left", fill="y", padx=(12, 0))
        logo = _load_logo_ctk(24)
        if logo:
            ctk.CTkLabel(left, image=logo, text="").pack(side="left", padx=(0, 8), pady=8)
        ctk.CTkLabel(
            left,
            text=config.APP_DISPLAY,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=theme.TEXT,
        ).pack(side="left", pady=8)

        right = ctk.CTkFrame(bar, fg_color="transparent")
        right.pack(side="right", fill="y", padx=(0, 4))

        def _wbtn(txt, cmd, w=40):
            ctk.CTkButton(
                right,
                text=txt,
                width=w,
                height=28,
                fg_color="transparent",
                hover_color=theme.DOCK_HANDLE,
                text_color=theme.TEXT_SOFT,
                font=ctk.CTkFont(size=14),
                corner_radius=6,
                command=cmd,
            ).pack(side="left", padx=1, pady=6)

        _wbtn("\u2014", self._minimize)
        _wbtn("\u25a1", self._toggle_maximize)
        _wbtn("\u2715", self.hide, w=44)

        self._bind_drag(bar)
        self._bind_drag(left)

        ctk.CTkFrame(parent, height=1, fg_color=theme.SEPARATOR).pack(fill="x")

    def _bind_drag(self, widget):
        widget.configure(cursor="fleur")
        widget.bind("<ButtonPress-1>", self._start_drag, add="+")
        widget.bind("<B1-Motion>", self._on_drag, add="+")

    def _start_drag(self, event):
        w = event.widget
        while w is not None:
            if w.winfo_class() == "CTkButton":
                return
            w = getattr(w, "master", None)
        self._drag_x = event.x_root
        self._drag_y = event.y_root
        self._win_x = self.winfo_x()
        self._win_y = self.winfo_y()

    def _on_drag(self, event):
        if not hasattr(self, "_win_x"):
            return
        x = self._win_x + event.x_root - self._drag_x
        y = self._win_y + event.y_root - self._drag_y
        self.geometry(f"+{x}+{y}")

    def _minimize(self):
        try:
            self.iconify()
        except Exception:
            self.withdraw()

    def _toggle_maximize(self):
        try:
            if self.state() == "zoomed":
                self.state("normal")
            else:
                self.state("zoomed")
        except Exception:
            pass

    def _build(self):
        root = ctk.CTkFrame(self, fg_color=theme.BG, corner_radius=0)
        root.pack(fill="both", expand=True)

        self._build_title_bar(root)

        body = ctk.CTkFrame(root, fg_color=theme.BG, corner_radius=0)
        body.pack(fill="both", expand=True)

        sidebar = ctk.CTkFrame(body, fg_color=theme.PANEL, width=_SIDEBAR_W, corner_radius=0)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        ctk.CTkFrame(sidebar, height=1, fg_color=theme.SEPARATOR).pack(fill="x", pady=(8, 6))

        for label_key, key in (
            ("nav.gallery", "gallery"),
            ("nav.clips", "recordings"),
            ("nav.settings", "settings"),
        ):
            b = ctk.CTkButton(
                sidebar,
                text=i18n.t(label_key),
                height=46,
                anchor="w",
                fg_color="transparent",
                hover_color=theme.DOCK_HANDLE,
                text_color=theme.NAV_INACTIVE,
                font=ctk.CTkFont(size=13),
                corner_radius=10,
                command=lambda k=key: self._nav(k),
            )
            b.pack(fill="x", padx=10, pady=3)
            self._nb[key] = b

        ctk.CTkFrame(sidebar, height=1, fg_color=theme.SEPARATOR).pack(fill="x", pady=(8, 10))

        self._save_btn = ctk.CTkButton(
            sidebar,
            text=i18n.t("home.save"),
            height=40,
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
            corner_radius=10,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=lambda: self.app.do_save() if self.app else None,
        )
        self._save_btn.pack(fill="x", padx=10, pady=(0, 6))

        self._toggle_btn = ctk.CTkButton(
            sidebar,
            text=i18n.t("home.cap_stop"),
            height=36,
            fg_color=theme.BTN_DARK,
            hover_color=theme.ACCENT_HOVER,
            border_width=1,
            border_color=theme.ACCENT_DEEP,
            corner_radius=10,
            font=ctk.CTkFont(size=12),
            command=lambda: self.app.do_toggle() if self.app else None,
        )
        self._toggle_btn.pack(fill="x", padx=10)

        try:
            from version import __version__
            ctk.CTkLabel(
                sidebar,
                text=f"v{__version__}",
                font=ctk.CTkFont(size=10),
                text_color=theme.VERSION_MUTED,
            ).pack(side="bottom", pady=8)
        except Exception:
            pass

        ctk.CTkFrame(body, width=1, fg_color=theme.SEPARATOR).pack(side="left", fill="y")

        self._content = ctk.CTkFrame(body, fg_color=theme.CBG, corner_radius=0)
        self._content.pack(side="right", fill="both", expand=True)

        grip = ctk.CTkFrame(self, width=14, height=14, fg_color="transparent", cursor="size_nw_se")
        grip.place(relx=1.0, rely=1.0, anchor="se")
        grip.bind("<ButtonPress-1>", self._resize_start)
        grip.bind("<B1-Motion>", self._resize_drag)

        from page_recordings import RecordingsPage
        from page_settings import SettingsPage

        self._pages = {
            "gallery": _GalleryPage(self._content, self.app),
            "recordings": RecordingsPage(self._content, app=self.app),
            "settings": SettingsPage(self._content, app=self.app),
        }
        for pg in self._pages.values():
            pg.place(relx=0, rely=0, relwidth=1, relheight=1)

        self._nav("gallery")

    def _nav(self, key: str):
        for k, pg in self._pages.items():
            if k == key:
                pg.place(relx=0, rely=0, relwidth=1, relheight=1)
            else:
                pg.place_forget()
        for k, b in self._nb.items():
            b.configure(
                fg_color=theme.ACCENT_DEEP if k == key else "transparent",
                text_color=theme.TEXT if k == key else theme.NAV_INACTIVE,
            )

    def _resize_start(self, event):
        self._rs_x = event.x_root
        self._rs_y = event.y_root
        self._rs_w = self.winfo_width()
        self._rs_h = self.winfo_height()

    def _resize_drag(self, event):
        try:
            nw = max(800, self._rs_w + event.x_root - self._rs_x)
            nh = max(520, self._rs_h + event.y_root - self._rs_y)
            self.geometry(f"{nw}x{nh}")
        except Exception:
            pass

    def show(self):
        try:
            if not self.winfo_exists():
                return
            if self.state() == "withdrawn":
                self.deiconify()
            self.lift()
            self.attributes("-topmost", True)
            self.after(80, lambda: self.attributes("-topmost", False))
            self.focus_force()
        except Exception:
            pass

    def hide(self):
        try:
            self.withdraw()
        except Exception:
            pass

    def toggle(self):
        try:
            if not self.winfo_exists():
                self.show()
                return
            if self.winfo_viewable():
                self.hide()
            else:
                self.show()
        except Exception:
            self.show()

    def refresh_gallery(self):
        p = self._pages.get("gallery")
        if p and hasattr(p, "refresh"):
            try:
                p.refresh()
            except Exception:
                pass
