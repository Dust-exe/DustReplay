import json
import logging
import os
import re
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
    def __init__(self, master, tag_name: str, changelog: str, release_url: str):
        super().__init__(master)
        self.tag_name = tag_name
        self.release_url = release_url

        v_name = tag_name if tag_name.startswith("v") else f"v{tag_name}"
        title_text = f"🎉 {i18n.t('updater_new_version')} ({v_name})"

        self.title(i18n.t("updater_title"))
        self.geometry("560x400")
        self.configure(fg_color=theme.BG)
        self.attributes("-topmost", True)
        self.resizable(False, False)

        self._build_ui(title_text, changelog)

    def _build_ui(self, title_text, changelog):
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=24, pady=24)

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
            height=200,
            fg_color=theme.ENTRY_BG,
            text_color=theme.TEXT,
            font=ctk.CTkFont(size=12),
        )
        self.textbox.pack(fill="both", expand=True, pady=(0, 16))
        self.textbox.insert("0.0", changelog if changelog else "No changelog provided.")
        self.textbox.configure(state="disabled")

        btn_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        btn_frame.pack(fill="x")

        btn_update = ctk.CTkButton(
            btn_frame,
            text=i18n.t("updater_btn_update"),
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
            height=36,
            font=ctk.CTkFont(weight="bold"),
            command=self._do_update,
        )
        btn_update.pack(side="right", padx=(10, 0))

        btn_later = ctk.CTkButton(
            btn_frame,
            text=i18n.t("updater_btn_later"),
            fg_color=theme.ENTRY_BG,
            hover_color=theme.HEADER_BG,
            text_color=theme.TEXT,
            height=36,
            command=self.destroy,
        )
        btn_later.pack(side="right")

    def _do_update(self):
        webbrowser.open(self.release_url)
        self.destroy()


def check_for_updates(app=None, manual=False, callback=None, main_window=None):
    """Check GitHub Releases for updates.
    
    Accepts app, main_window, or callback to ensure compatibility with all callers.
    """
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

                remote_v = _parse_version(tag_name)
                local_v = _parse_version(version.__version__)

                logger.info(
                    "Update check: remote=%s local=%s (tag=%s)",
                    remote_v,
                    local_v,
                    tag_name,
                )

                if remote_v > local_v:
                    if callback:
                        callback(tag_name, body, html_url)
                    elif target_app and hasattr(target_app, "after"):
                        target_app.after(
                            0, lambda: UpdateDialog(target_app, tag_name, body, html_url)
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
