import logging
import os
import re
import subprocess
import threading
from datetime import timedelta
import customtkinter as ctk

import config
import i18n
import theme
from clip_editor import TimelineRangeBar

logger = logging.getLogger(__name__)


class GifMakerDialog(ctk.CTkToplevel):
    def __init__(self, master, video_path: str, on_complete: callable = None):
        super().__init__(master)
        self.video_path = video_path
        self.on_complete = on_complete

        self.title(i18n.t("gif_maker_title"))
        self.geometry("700x500")
        self.overrideredirect(True)
        self.configure(fg_color=theme.BG)
        self.attributes("-topmost", True)

        self.duration = self._get_duration()
        self.start_val = 0.0
        self.end_val = min(self.duration, 15.0)

        self._build_ui()

    def _get_duration(self) -> float:
        try:
            ff = config.resolve_ffmpeg_exe()
            if not ff:
                return 0.0

            r = subprocess.run(
                [ff, "-i", self.video_path],
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

            match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.\d+)", r.stderr)
            if match:
                h, m, s = match.groups()
                return float(h) * 3600 + float(m) * 60 + float(s)

            for line in r.stderr.splitlines():
                if "Duration:" in line:
                    parts = line.split("Duration:")[1].split(",")[0].strip()
                    h, m, s = parts.split(":")
                    return float(h) * 3600 + float(m) * 60 + float(s)

            return 0.0
        except Exception as e:
            logger.error("Failed to get duration: %s", e)
            return 0.0

    def _format_time(self, seconds: float) -> str:
        s = max(0, min(self.duration, seconds))
        return str(timedelta(seconds=int(s)))[2:]

    def _build_ui(self):
        # Title bar
        self.title_bar = ctk.CTkFrame(self, fg_color=theme.HEADER_BG, corner_radius=0, height=40)
        self.title_bar.pack(fill="x")
        self.title_bar.pack_propagate(False)
        self.title_bar.bind("<ButtonPress-1>", self._start_move)
        self.title_bar.bind("<B1-Motion>", self._do_move)

        lbl_title = ctk.CTkLabel(
            self.title_bar,
            text=i18n.t("gif_maker_title"),
            font=ctk.CTkFont(weight="bold", size=14),
            text_color=theme.TEXT,
        )
        lbl_title.pack(side="left", padx=15)
        lbl_title.bind("<ButtonPress-1>", self._start_move)
        lbl_title.bind("<B1-Motion>", self._do_move)

        btn_close = ctk.CTkButton(
            self.title_bar,
            text="✕",
            width=30,
            height=30,
            fg_color="transparent",
            hover_color=theme.RED,
            command=self.destroy,
        )
        btn_close.pack(side="right", padx=5)

        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        # Selected Duration prominently displayed
        self.lbl_selected_range = ctk.CTkLabel(
            self.main_frame,
            text=self._get_range_text(),
            font=ctk.CTkFont(weight="bold", size=14),
            text_color=theme.TEXT,
        )
        self.lbl_selected_range.pack(pady=(10, 5))

        # Single unified dual-thumb timeline range bar
        self.range_bar = TimelineRangeBar(
            self.main_frame,
            duration=self.duration,
            on_change=self._on_range_changed,
        )
        self.range_bar.set_range(self.start_val, self.end_val)
        self.range_bar.pack(fill="x", pady=10, padx=10)

        # Settings controls
        settings_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        settings_frame.pack(pady=10)

        ctk.CTkLabel(settings_frame, text=i18n.t("gif_fps")).grid(row=0, column=0, padx=10, pady=10, sticky="e")
        self.seg_fps = ctk.CTkSegmentedButton(
            settings_frame,
            values=["10", "15", "20"],
            selected_color=theme.ACCENT,
            selected_hover_color=theme.ACCENT_HOVER,
            command=self._update_estimate,
        )
        self.seg_fps.set("15")
        self.seg_fps.grid(row=0, column=1, pady=10, sticky="w")

        ctk.CTkLabel(settings_frame, text=i18n.t("gif_resolution")).grid(row=1, column=0, padx=10, pady=10, sticky="e")
        self.seg_res = ctk.CTkSegmentedButton(
            settings_frame,
            values=["480p", "360p", "240p"],
            selected_color=theme.ACCENT,
            selected_hover_color=theme.ACCENT_HOVER,
            command=self._update_estimate,
        )
        self.seg_res.set("360p")
        self.seg_res.grid(row=1, column=1, pady=10, sticky="w")

        self.lbl_warning = ctk.CTkLabel(self.main_frame, text="", text_color=theme.WARNING)
        self.lbl_warning.pack(pady=2)

        self.lbl_estimate = ctk.CTkLabel(self.main_frame, text="", text_color=theme.TEXT_SOFT)
        self.lbl_estimate.pack(pady=2)

        # BIG Obvious Create Button
        self.btn_create = ctk.CTkButton(
            self.main_frame,
            text=i18n.t("gif_create"),
            font=ctk.CTkFont(weight="bold", size=16),
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
            height=40,
            command=self._do_create,
        )
        self.btn_create.pack(pady=(10, 5), fill="x", padx=40)

        # Progress and Action
        self.progress = ctk.CTkProgressBar(self.main_frame, progress_color=theme.ACCENT)
        self.progress.set(0)

        self.lbl_status = ctk.CTkLabel(self.main_frame, text="", text_color=theme.TEXT_SOFT)
        self.lbl_status.pack(pady=2)

        self._update_estimate()

    def _get_range_text(self):
        sel_dur = max(0, self.end_val - self.start_val)
        return f"✂️ {i18n.t('clip_selected_range')}: {self._format_time(self.start_val)} → {self._format_time(self.end_val)} ({int(sel_dur)} {i18n.t('clip_seconds')})"

    def _update_range_text(self):
        self.lbl_selected_range.configure(text=self._get_range_text())

    def _start_move(self, event):
        self._x = event.x
        self._y = event.y

    def _do_move(self, event):
        deltax = event.x - self._x
        deltay = event.y - self._y
        x = self.winfo_x() + deltax
        y = self.winfo_y() + deltay
        self.geometry(f"+{x}+{y}")

    def _on_range_changed(self, start, end):
        self.start_val = start
        self.end_val = end
        self._check_duration()
        self._update_range_text()

    def _check_duration(self):
        dur = self.end_val - self.start_val
        if dur > 15.0:
            self.lbl_warning.configure(text=i18n.t("gif_max_duration_warning"))
        else:
            self.lbl_warning.configure(text="")
        self._update_estimate()

    def _update_estimate(self, *_):
        dur = max(0, self.end_val - self.start_val)
        fps = int(self.seg_fps.get())
        res = int(self.seg_res.get().replace("p", ""))

        est_mb = dur * fps * (res / 360) * 0.1
        self.lbl_estimate.configure(text=f"{i18n.t('gif_estimated_size')}: ~{est_mb:.1f} MB")

    def _do_create(self):
        self.btn_create.configure(state="disabled")
        self.progress.pack(fill="x", pady=10)
        self.progress.start()
        self.lbl_status.configure(text=i18n.t("gif_creating"), text_color=theme.TEXT_SOFT)

        fps = self.seg_fps.get()
        height = self.seg_res.get().replace("p", "")
        start_v = self.start_val
        end_v = self.end_val

        threading.Thread(
            target=self._create_worker,
            args=(fps, height, start_v, end_v),
            daemon=True,
        ).start()

    def _create_worker(self, fps, height, start_v, end_v):
        try:
            ff = config.resolve_ffmpeg_exe()
            if not ff:
                raise Exception("ffmpeg executable not found.")

            # Save GIFs directly to user's Downloads folder
            od = os.path.join(os.path.expanduser("~"), "Downloads")
            os.makedirs(od, exist_ok=True)

            f = os.path.basename(self.video_path)
            n, _ = os.path.splitext(f)
            out_path = os.path.join(od, f"{n}.gif")

            if height == "480":
                width = 854
            elif height == "360":
                width = 640
            else:
                width = 426

            dur = max(0.5, end_v - start_v)

            cmd = [
                ff, "-y",
                "-ss", f"{start_v:.2f}",
                "-t", f"{dur:.2f}",
                "-i", self.video_path,
                "-filter_complex", f"[0:v]fps={fps},scale={width}:-1:flags=lanczos,split[s0][s1];[s0]palettegen=stats_mode=diff[p];[s1][p]paletteuse=dither=bayer:bayer_scale=5",
                out_path,
            ]

            r = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )

            if r.returncode != 0 or not os.path.isfile(out_path) or os.path.getsize(out_path) == 0:
                logger.warning("Single-pass complex GIF filter failed, trying fallback. Stderr: %s", r.stderr)
                cmd_fb = [
                    ff, "-y",
                    "-ss", f"{start_v:.2f}",
                    "-t", f"{dur:.2f}",
                    "-i", self.video_path,
                    "-vf", f"fps={fps},scale={width}:-1:flags=lanczos",
                    out_path,
                ]
                r_fb = subprocess.run(
                    cmd_fb,
                    capture_output=True,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                if r_fb.returncode != 0 or not os.path.isfile(out_path) or os.path.getsize(out_path) == 0:
                    err_msg = r_fb.stderr[-250:] if r_fb.stderr else (r.stderr[-250:] if r.stderr else "GIF encoding failed")
                    raise Exception(err_msg)

            self.after(0, self._on_success, out_path)
        except Exception as e:
            self.after(0, self._on_error, str(e))

    def _on_success(self, out_path):
        self.progress.stop()
        self.progress.set(1.0)
        self.lbl_status.configure(
            text=f"{i18n.t('gif_done')} -> Downloads/{os.path.basename(out_path)}",
            text_color=theme.GREEN,
        )
        self.btn_create.configure(state="normal")
        if self.on_complete:
            self.on_complete()

    def _on_error(self, err):
        self.progress.stop()
        self.lbl_status.configure(text=f"{i18n.t('clip_error')}: {err}", text_color=theme.RED)
        self.btn_create.configure(state="normal")
