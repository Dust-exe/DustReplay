import os
import threading
import urllib.request
import zipfile

import config
import customtkinter as ctk

FFMPEG_URL = (
    "https://github.com/BtbN/ffmpeg-builds/releases/download/latest/"
    "ffmpeg-master-latest-win64-gpl.zip"
)
FFMPEG_EXE = os.path.join(config.APPDATA_DIR, "ffmpeg", "ffmpeg.exe")


def ffmpeg_ready():
    return os.path.isfile(FFMPEG_EXE)


def ensure_ffmpeg():
    if ffmpeg_ready():
        return
    _DL().run()


class _DL:
    def __init__(self):
        ctk.set_appearance_mode("dark")
        self.root = ctk.CTk()
        self.root.title("DustReplay — First run")
        self.root.geometry("480x300")
        self.root.resizable(False, False)
        self.root.configure(fg_color="#0d0019")
        self.root.protocol("WM_DELETE_WINDOW", lambda: None)
        self.root.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"480x300+{(sw - 480) // 2}+{(sh - 300) // 2}")
        ctk.CTkLabel(
            self.root,
            text="\u25cf DustReplay",
            font=ctk.CTkFont(size=24, weight="bold"),
            text_color="#9933ff",
        ).pack(pady=(30, 0))
        ctk.CTkLabel(
            self.root,
            text="Downloading ffmpeg (~80 MB)…",
            font=ctk.CTkFont(size=12),
            text_color="#aa77ff",
        ).pack(pady=(4, 20))
        self.bar = ctk.CTkProgressBar(
            self.root,
            height=14,
            progress_color="#9933ff",
            fg_color="#2a004a",
            corner_radius=6,
        )
        self.bar.pack(padx=48, fill="x")
        self.bar.set(0)
        self.st = ctk.CTkLabel(
            self.root,
            text="Connecting…",
            font=ctk.CTkFont(size=12),
            text_color="#bb88ff",
        )
        self.st.pack(pady=(14, 0))
        self.pc = ctk.CTkLabel(
            self.root,
            text="0%",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#9933ff",
        )
        self.pc.pack()
        ctk.CTkLabel(
            self.root,
            text="This download runs once.",
            font=ctk.CTkFont(size=11),
            text_color="#3d1080",
        ).pack(pady=(10, 0))
        self._ok = False
        self._err = None

    def _set(self, s, p):
        self.root.after(0, lambda: self.st.configure(text=s))
        self.root.after(0, lambda: self.pc.configure(text=f"{int(p * 100)}%"))
        self.root.after(0, lambda: self.bar.set(p))

    def _dl(self):
        try:
            dd = os.path.join(config.APPDATA_DIR, "ffmpeg")
            os.makedirs(dd, exist_ok=True)
            zt = os.path.join(config.APPDATA_DIR, "_ff.zip")

            def prog(bn, bs, ts):
                if ts > 0:
                    self._set(
                        f"Downloading… {bn * bs / 1048576:.1f}/{ts / 1048576:.0f} MB",
                        min(bn * bs / ts, 1.0) * 0.85,
                    )

            urllib.request.urlretrieve(FFMPEG_URL, zt, prog)
            self._set("Extracting…", 0.88)
            with zipfile.ZipFile(zt, "r") as z:
                for m in z.namelist():
                    if m.endswith("ffmpeg.exe"):
                        with z.open(m) as src, open(FFMPEG_EXE, "wb") as dst:
                            dst.write(src.read())
                        break
            try:
                os.remove(zt)
            except Exception:
                pass
            if not os.path.isfile(FFMPEG_EXE):
                raise FileNotFoundError("ffmpeg.exe not found in archive.")
            self._set("Ready.", 1.0)
            self._ok = True
            self.root.after(900, self.root.destroy)
        except Exception as e:
            self._err = str(e)
            self.root.after(
                0,
                lambda: self.st.configure(text=f"Error: {e}", text_color="#ff4444"),
            )

    def run(self):
        threading.Thread(target=self._dl, daemon=True).start()
        self.root.mainloop()
        if not self._ok:
            import ctypes
            import sys

            ctypes.windll.user32.MessageBoxW(
                0,
                f"Could not download ffmpeg:\n{self._err}",
                "DustReplay",
                0x10,
            )
            sys.exit(1)
