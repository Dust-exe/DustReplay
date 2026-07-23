import json
import logging
import os
import subprocess
import threading
import urllib.request
import webbrowser
import customtkinter as ctk

import config
import i18n
import theme
import version

logger = logging.getLogger(__name__)

class UpdateDialog(ctk.CTkToplevel):
    def __init__(self, master, tag_name: str, changelog: str, release_url: str):
        super().__init__(master)
        self.tag_name = tag_name
        self.release_url = release_url
        
        # Parse version string nicely if needed
        v_name = tag_name if tag_name.startswith('v') else f"v{tag_name}"
        title_text = f"🎉 {i18n.t('updater_new_version')} ({v_name})"
        
        self.title(i18n.t("updater_title"))
        self.geometry("550x380")
        self.configure(fg_color=theme.BG)
        self.attributes("-topmost", True)
        
        # Build UI
        self._build_ui(title_text, changelog)
        
    def _build_ui(self, title_text, changelog):
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        lbl_title = ctk.CTkLabel(self.main_frame, text=title_text, font=ctk.CTkFont(weight="bold", size=18), text_color=theme.TEXT)
        lbl_title.pack(pady=(0, 10))
        
        lbl_changelog = ctk.CTkLabel(self.main_frame, text=i18n.t("updater_changelog"), text_color=theme.TEXT_SOFT)
        lbl_changelog.pack(anchor="w")
        
        self.textbox = ctk.CTkTextbox(self.main_frame, width=500, height=200, fg_color=theme.ENTRY_BG, text_color=theme.TEXT)
        self.textbox.pack(fill="both", expand=True, pady=(5, 15))
        self.textbox.insert("0.0", changelog)
        self.textbox.configure(state="disabled")
        
        # Buttons
        btn_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        btn_frame.pack(fill="x")
        
        btn_update = ctk.CTkButton(btn_frame, text=i18n.t("updater_btn_update"), fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER, command=self._do_update)
        btn_update.pack(side="right", padx=(10, 0))
        
        btn_later = ctk.CTkButton(btn_frame, text=i18n.t("updater_btn_later"), fg_color=theme.ENTRY_BG, hover_color=theme.HEADER_BG, text_color=theme.TEXT, command=self.destroy)
        btn_later.pack(side="right")

    def _do_update(self):
        # Open default browser to download
        webbrowser.open(self.release_url)
        self.destroy()

def check_for_updates(manual=False, callback=None, main_window=None):
    def worker():
        try:
            req = urllib.request.Request(
                "https://api.github.com/repos/Dust-exe/DustReplay/releases/latest",
                headers={"User-Agent": "DustReplay-Updater"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                
                tag_name = data.get("tag_name", "")
                body = data.get("body", "")
                html_url = data.get("html_url", "")
                
                # Check version
                # Basic strip 'v' if present for comparison
                remote_version = tag_name.lstrip('v')
                local_version = version.__version__.lstrip('v')
                
                # Compare versions (simple logic)
                if remote_version and remote_version != local_version:
                    # Can enhance comparison logic
                    if callback:
                        callback(tag_name, body, html_url)
                else:
                    if manual and main_window:
                        # Assuming there's a toast/notification system, or fallback to simple dialog
                        from tkinter import messagebox
                        messagebox.showinfo(i18n.t("updater_title"), i18n.t("updater_up_to_date"))

        except Exception as e:
            logger.error("Failed to check for updates: %s", e)

    threading.Thread(target=worker, daemon=True).start()
