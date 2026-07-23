import logging
import os
import re
import subprocess
import threading
from datetime import timedelta
import customtkinter as ctk
from PIL import Image

import config
import i18n
import theme

logger = logging.getLogger(__name__)


class TimelineRangeBar(ctk.CTkCanvas):
    """Unified single-bar dual-thumb range selector for timeline trimming."""

    def __init__(self, master, duration: float, on_change=None, **kwargs):
        super().__init__(master, height=36, bg="#12111c", highlightthickness=0, **kwargs)
        self.duration = max(0.1, duration)
        self.on_change = on_change
        self.start_val = 0.0
        self.end_val = self.duration
        self._dragging = None

        self.bind("<Button-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Configure>", self._redraw)

    def set_range(self, start, end):
        self.start_val = max(0.0, min(self.duration, start))
        self.end_val = max(self.start_val + 0.5, min(self.duration, end))
        self._redraw()

    def _redraw(self, event=None):
        self.delete("all")
        w = max(100, self.winfo_width())
        h = max(20, self.winfo_height())

        # Dark track background
        self.create_rectangle(0, 0, w, h, fill="#12111c", outline="#28263a", width=1)

        x_start = int((self.start_val / self.duration) * w)
        x_end = int((self.end_val / self.duration) * w)

        # Selected range highlight
        if x_end > x_start:
            self.create_rectangle(x_start, 2, x_end, h - 2, fill=theme.ACCENT, outline="")

        # Left handle knob
        self.create_rectangle(max(0, x_start - 7), 0, min(w, x_start + 7), h, fill="#a29bfe", outline="#ffffff", width=1)
        self.create_line(x_start, 6, x_start, h - 6, fill="#12111c", width=2)

        # Right handle knob
        self.create_rectangle(max(0, x_end - 7), 0, min(w, x_end + 7), h, fill="#a29bfe", outline="#ffffff", width=1)
        self.create_line(x_end, 6, x_end, h - 6, fill="#12111c", width=2)

    def _on_press(self, event):
        w = max(100, self.winfo_width())
        x_start = int((self.start_val / self.duration) * w)
        x_end = int((self.end_val / self.duration) * w)

        if abs(event.x - x_start) <= 18:
            self._dragging = "start"
        elif abs(event.x - x_end) <= 18:
            self._dragging = "end"
        else:
            if abs(event.x - x_start) < abs(event.x - x_end):
                self._dragging = "start"
            else:
                self._dragging = "end"
            self._on_drag(event)

    def _on_drag(self, event):
        if not self._dragging:
            return
        w = max(100, self.winfo_width())
        val = max(0.0, min(self.duration, (event.x / w) * self.duration))

        if self._dragging == "start":
            self.start_val = min(val, self.end_val - 0.5)
        elif self._dragging == "end":
            self.end_val = max(val, self.start_val + 0.5)

        self._redraw()
        if self.on_change:
            self.on_change(self.start_val, self.end_val)

    def _on_release(self, event):
        self._dragging = None


class ClipEditor(ctk.CTkToplevel):
    def __init__(self, master, video_path: str, on_complete: callable = None):
        super().__init__(master)
        self.video_path = video_path
        self.on_complete = on_complete

        self.title(i18n.t("clip_editor_title"))
        self.geometry("700x500")
        self.overrideredirect(True)
        self.configure(fg_color=theme.BG)
        self.attributes("-topmost", True)

        self.duration = self._get_duration()
        self.start_val = 0.0
        self.end_val = self.duration

        self._build_ui()
        self._extract_thumbnails()

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
            text=i18n.t("clip_editor_title"),
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

        # Duration label
        self.lbl_duration = ctk.CTkLabel(
            self.main_frame,
            text=f"{i18n.t('clip_duration')}: {self._format_time(self.duration)}",
            text_color=theme.TEXT_SOFT,
        )
        self.lbl_duration.pack(pady=(0, 10))

        # Thumbnails frame
        self.thumbs_frame = ctk.CTkFrame(self.main_frame, height=76, fg_color=theme.ENTRY_BG)
        self.thumbs_frame.pack(fill="x", pady=5)
        self.thumbs_frame.pack_propagate(False)
        self.thumb_labels = []
        for i in range(5):
            lbl = ctk.CTkLabel(self.thumbs_frame, text="...")
            lbl.pack(side="left", expand=True, fill="both", padx=2)
            self.thumb_labels.append(lbl)

        # Selected Duration prominently displayed
        self.lbl_selected_range = ctk.CTkLabel(
            self.main_frame,
            text=self._get_range_text(),
            font=ctk.CTkFont(weight="bold", size=14),
            text_color=theme.TEXT,
        )
        self.lbl_selected_range.pack(pady=(10, 5))

        # Unified single-bar dual-thumb Range Bar
        self.range_bar = TimelineRangeBar(
            self.main_frame,
            duration=self.duration,
            on_change=self._on_range_changed,
        )
        self.range_bar.pack(fill="x", pady=10, padx=10)

        # Mode selection
        mode_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        mode_frame.pack(pady=10)
        ctk.CTkLabel(mode_frame, text=i18n.t("clip_trim_mode")).pack(side="left", padx=10)
        self.seg_mode = ctk.CTkSegmentedButton(
            mode_frame,
            values=[i18n.t("clip_copy_fast"), i18n.t("clip_reencode_precise")],
            selected_color=theme.ACCENT,
            selected_hover_color=theme.ACCENT_HOVER,
        )
        self.seg_mode.set(i18n.t("clip_copy_fast"))
        self.seg_mode.pack(side="left")

        # BIG Obvious trim button
        self.btn_trim = ctk.CTkButton(
            self.main_frame,
            text=i18n.t("clip_trim"),
            font=ctk.CTkFont(weight="bold", size=16),
            fg_color=theme.ACCENT,
            hover_color=theme.ACCENT_HOVER,
            height=40,
            command=self._do_trim,
        )
        self.btn_trim.pack(pady=(15, 5), fill="x", padx=40)

        # Progress and Action
        self.progress = ctk.CTkProgressBar(self.main_frame, progress_color=theme.ACCENT)
        self.progress.set(0)

        self.lbl_status = ctk.CTkLabel(self.main_frame, text="", text_color=theme.TEXT_SOFT)
        self.lbl_status.pack(pady=2)

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
        self._update_range_text()

    def _extract_thumbnails(self):
        if self.duration <= 0:
            return
        threading.Thread(target=self._thumb_worker, daemon=True).start()

    def _thumb_worker(self):
        ff = config.resolve_ffmpeg_exe()
        if not ff:
            return

        temp_dir = os.path.join(config.APPDATA_DIR, "thumbs")
        os.makedirs(temp_dir, exist_ok=True)

        step = self.duration / 5
        for i in range(5):
            t = step * i + (step / 2)
            out_p = os.path.join(temp_dir, f"thumb_{i}.jpg")
            cmd = [
                ff, "-y", "-ss", str(t), "-i", self.video_path,
                "-vframes", "1", "-vf", "scale=120:-1", out_p
            ]
            subprocess.run(cmd, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)

            if os.path.isfile(out_p):
                try:
                    pil = Image.open(out_p)
                    img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(pil.width, pil.height))
                    self.after(0, lambda idx=i, im=img: self._set_thumb(idx, im))
                except Exception as e:
                    logger.debug("Thumb error: %s", e)

    def _set_thumb(self, idx, img):
        if idx < len(self.thumb_labels):
            self.thumb_labels[idx].configure(image=img, text="")
            self.thumb_labels[idx]._dr_img = img

    def _do_trim(self):
        self.btn_trim.configure(state="disabled")
        self.progress.pack(fill="x", pady=10)
        self.progress.start()
        self.lbl_status.configure(text=i18n.t("clip_trimming"), text_color=theme.TEXT_SOFT)

        mode = self.seg_mode.get()
        threading.Thread(target=self._trim_worker, args=(mode,), daemon=True).start()

    def _trim_worker(self, mode):
        try:
            ff = config.resolve_ffmpeg_exe()
            d, f = os.path.split(self.video_path)
            n, e = os.path.splitext(f)
            out_path = os.path.join(d, f"{n}_trimmed{e}")

            cmd = [
                ff, "-y", "-ss", f"{self.start_val:.2f}", "-to", f"{self.end_val:.2f}",
                "-i", self.video_path
            ]

            if mode == i18n.t("clip_copy_fast"):
                cmd.extend(["-c", "copy", "-avoid_negative_ts", "make_zero", out_path])
            else:
                cmd.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "18", "-c:a", "aac", out_path])

            r = subprocess.run(cmd, capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)

            if r.returncode == 0:
                self.after(0, self._on_success, out_path)
            else:
                err = r.stderr[-200:] if r.stderr else "Unknown error"
                self.after(0, self._on_error, err)
        except Exception as e:
            self.after(0, self._on_error, str(e))

    def _on_success(self, out_path):
        self.progress.stop()
        self.progress.set(1.0)
        self.lbl_status.configure(
            text=f"{i18n.t('clip_done')} -> {os.path.basename(out_path)}",
            text_color=theme.GREEN,
        )
        self.btn_trim.configure(state="normal")
        if self.on_complete:
            self.on_complete()

    def _on_error(self, err):
        self.progress.stop()
        self.lbl_status.configure(text=f"{i18n.t('clip_error')}: {err}", text_color=theme.RED)
        self.btn_trim.configure(state="normal")
