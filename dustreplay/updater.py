import json
import logging
import os
import re
import subprocess
import sys
import threading
import urllib.request
import webbrowser
import customtkinter as ctk
from tkinter import messagebox

import config
import i18n
import theme
import version

logger = logging.getLogger(__name__)


def _parse_version(v_str: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+", str(v_str))
    return tuple(int(x) for x in nums) if nums else (0,)


class UpdateDialog(ctk.CTkToplevel):
    def __init__(self, master, tag_name: str, changelog: str, release_url: str, download_url: str = None):
        super().__init__(master)
        self.tag_name = tag_name
        self.release_url = release_url
        self.download_url = download_url

        v_name = tag_name if tag_name.startswith("v") else f"v{tag_name}"
        title_text = f"🎉 {i18n.t('updater_new_version')} ({v_name})"

        self.title(i18n.t("updater_title"))
        self.geometry("560x420")
        self.configure(fg_color=theme.BG)
        self.attributes("-topmost", True)
        self.resizable(False, False)

        self._build_ui(title_text, changelog)

    def _build_ui(self, title_text, changelog):
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=24, pady=20)

        lbl_title = ctk.CTkLabel(
            self.main_frame,
            text=title_text,
            font=ctk.CTkFont(weight="bold", size=18),
            text_color=theme.TEXT,
        )
        lbl_title.pack(pady=(0, 10))

        lbl_changelog = ctk.CTkLabel(
            self.main_frame,
            text=i18n.t("updater_changelog"),
            text_color=theme.TEXT_SOFT,
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        lbl_changelog.pack(anchor="w", pady=(0, 4))

        self.textbox = ctk.CTkTextbox(
            self.main_frame,
            width=500,
            height=180,
            fg_color=theme.ENTRY_BG,
            text_color=theme.TEXT,
            font=ctk.CTkFont(size=12),
        )
        self.textbox.pack(fill="both", expand=True, pady=(0, 12))
        self.textbox.insert("0.0", changelog if changelog else "No changelog provided.")
        self.textbox.configure(state="disabled")

        # Progress bar (hidden until download starts)
        self.progress = ctk.CTkProgressBar(self.main_frame, progress_color=theme.ACCENT)
        self.progress.set(0)

        self.lbl_status = ctk.CTkLabel(self.main_frame, text="", text_color=theme.TEXT_SOFT, font=ctk.CTkFont(size=11))
        self.lbl_status.pack(pady=(0, 8))

        btn_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        btn_frame.pack(fill="x")

        self.btn_update = ctk.CTkButton(
            btn_frame,
            text=i18n.t("updater_btn_update"),
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
            height=36,
            font=ctk.CTkFont(weight="bold"),
            command=self._do_update,
        )
        self.btn_update.pack(side="right", padx=(10, 0))

        self.btn_later = ctk.CTkButton(
            btn_frame,
            text=i18n.t("updater_btn_later"),
            fg_color=theme.ENTRY_BG,
            hover_color=theme.HEADER_BG,
            text_color=theme.TEXT,
            height=36,
            command=self.destroy,
        )
        self.btn_later.pack(side="right")

    def _do_update(self):
        if not self.download_url:
            webbrowser.open(self.release_url)
            self.destroy()
            return

        self.btn_update.configure(state="disabled")
        self.btn_later.configure(state="disabled")
        self.progress.pack(fill="x", pady=(0, 8))
        self.lbl_status.configure(text="İndiriliyor...")

        threading.Thread(target=self._download_and_install_worker, daemon=True).start()

    def _download_and_install_worker(self):
        try:
            target_setup = os.path.join(config.TEMP_DIR, "DustReplay-Setup.exe")
            
            def _reporthook(count, block_size, total_size):
                if total_size > 0:
                    pct = min(1.0, (count * block_size) / total_size)
                    self.after(0, lambda: self._update_progress(pct, f"İndiriliyor: %{int(pct * 100)}"))

            req = urllib.request.Request(self.download_url, headers={"User-Agent": "DustReplay-Updater"})
            with urllib.request.urlopen(req, timeout=60) as response, open(target_setup, 'wb') as out_file:
                total_size = int(response.info().get('Content-Length', 0))
                bytes_so_far = 0
                chunk_size = 65536
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    out_file.write(chunk)
                    bytes_so_far += len(chunk)
                    if total_size > 0:
                        pct = min(1.0, bytes_so_far / total_size)
                        self.after(0, lambda p=pct: self._update_progress(p, f"İndiriliyor: %{int(p * 100)}"))

            self.after(0, lambda: self._update_progress(1.0, "Kurulum başlatılıyor..."))

            # Execute installer silently and quit current app
            if os.path.isfile(target_setup) and os.path.getsize(target_setup) > 10000:
                cmd = [target_setup, "/SILENT", "/CLOSEAPPLICATIONS", "/RESTARTAPPLICATIONS"]
                subprocess.Popen(cmd, creationflags=subprocess.CREATE_NO_WINDOW)
                self.after(500, lambda: os._exit(0))
            else:
                raise Exception("Downloaded setup file is invalid.")

        except Exception as e:
            logger.error("Auto download update failed: %s", e)
            self.after(0, lambda: self._on_download_error(str(e)))

    def _update_progress(self, pct, status_text):
        self.progress.set(pct)
        self.lbl_status.configure(text=status_text)

    def _on_download_error(self, err_msg):
        self.progress.pack_forget()
        self.lbl_status.configure(text=f"İndirme hatası: {err_msg}", text_color=theme.RED)
        self.btn_update.configure(state="normal", text="Tarayıcıda Aç", command=lambda: webbrowser.open(self.release_url))
        self.btn_later.configure(state="normal")


def check_for_updates(app=None, manual=False, callback=None, main_window=None):
    """Check GitHub Releases for updates."""
    target_app = app or main_window

    def worker():
        try:
            req = urllib.request.Request(
                "https://api.github.com/repos/Dust-exe/DustReplay/releases/latest",
                headers={"User-Agent": "DustReplay-Updater"},
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())

                tag_name = data.get("tag_name", "")
                body = data.get("body", "")
                html_url = data.get("html_url", "")

                download_url = None
                for asset in data.get("assets", []):
                    name = asset.get("name", "").lower()
                    if name.endswith(".exe"):
                        download_url = asset.get("browser_download_url")
                        break

                remote_v = _parse_version(tag_name)
                local_v = _parse_version(version.__version__)

                logger.info(
                    "Update check: remote=%s local=%s (tag=%s, download_url=%s)",
                    remote_v,
                    local_v,
                    tag_name,
                    download_url,
                )

                if remote_v > local_v:
                    if callback:
                        callback(tag_name, body, html_url)
                    elif target_app and hasattr(target_app, "after"):
                        target_app.after(
                            0, lambda: UpdateDialog(target_app, tag_name, body, html_url, download_url)
                        )
                else:
                    if manual:
                        if target_app and hasattr(target_app, "after"):
                            target_app.after(
                                0,
                                lambda: messagebox.showinfo(
                                    i18n.t("updater_title"), i18n.t("updater_up_to_date")
                                ),
                            )

        except Exception as e:
            logger.error("Failed to check for updates: %s", e)
            if manual and target_app and hasattr(target_app, "after"):
                target_app.after(
                    0,
                    lambda: messagebox.showerror(
                        i18n.t("updater_title"), f"Error checking for updates: {e}"
                    ),
                )

    threading.Thread(target=worker, daemon=True).start()
