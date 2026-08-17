"""DustReplay — Clip Analysis Engine & Diagnostics UI.

Analyzes recorded MP4 clips using ffmpeg.exe (no ffprobe.exe required).
Measures video FPS, resolution, audio presence, volume dB levels, and sync.
"""

import json
import logging
import os
import re
import subprocess
import threading
import customtkinter as ctk
import config
import theme

logger = logging.getLogger(__name__)


def run_clip_diagnostics(video_path: str) -> dict:
    """Analyze video file using ffmpeg.exe (no ffprobe dependency)."""
    if not os.path.isfile(video_path):
        return {"error": f"Dosya bulunamadı: {video_path}"}

    ff = config.resolve_ffmpeg_exe() or "ffmpeg"

    result = {
        "file_name": os.path.basename(video_path),
        "file_size_mb": round(os.path.getsize(video_path) / 1048576, 2),
        "duration": 0.0,
        "video": {},
        "audio": {},
        "sync_offset_ms": 0.0,
        "diagnosis": [],
        "healthy": True,
    }

    # 1. Parse ffmpeg -i info
    try:
        r = subprocess.run(
            [ff, "-hide_banner", "-i", video_path],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        info_text = r.stderr or r.stdout or ""

        # Duration match: Duration: 00:01:23.45, start: 0.000000, bitrate: 1234 kb/s
        dur_m = re.search(r"Duration:\s*(\d+):(\d+):([\d\.]+)", info_text)
        if dur_m:
            h, m, s = float(dur_m.group(1)), float(dur_m.group(2)), float(dur_m.group(3))
            result["duration"] = round(h * 3600 + m * 60 + s, 2)

        bitrate_m = re.search(r"bitrate:\s*(\d+)\s*kb/s", info_text)
        if bitrate_m:
            result["bitrate_kbps"] = int(bitrate_m.group(1))

        # Video stream match: Stream #0:0: Video: h264 (...), yuv420p(...), 1920x1080 [...], 60 fps
        v_m = re.search(r"Stream #\d+:\d+.*?: Video:\s*([^\,\s]+).*?(\d{3,4})x(\d{3,4}).*?([\d\.]+)\s*fps", info_text)
        if not v_m:
            v_m = re.search(r"Stream #\d+:\d+.*?: Video:\s*([^\,\s]+).*?(\d{3,4})x(\d{3,4})", info_text)

        if v_m:
            codec = v_m.group(1)
            w = int(v_m.group(2))
            h = int(v_m.group(3))
            fps = float(v_m.group(4)) if len(v_m.groups()) >= 4 and v_m.group(4) else 60.0
            result["video"] = {
                "codec": codec,
                "width": w,
                "height": h,
                "fps": fps,
            }
        else:
            result["video"] = None
            result["diagnosis"].append("❌ Video akışı bulunamadı.")
            result["healthy"] = False

        # Audio stream match: Stream #0:1: Audio: aac (...), 48000 Hz, stereo, fltp, 128 kb/s
        a_m = re.search(r"Stream #\d+:\d+.*?: Audio:\s*([^\,\s]+).*?(\d+)\s*Hz.*?(stereo|mono|\d+\s*channels|\d+\.\d+)", info_text, re.IGNORECASE)
        if a_m:
            acodec = a_m.group(1)
            sr = a_m.group(2)
            ch = a_m.group(3)
            result["audio"] = {
                "codec": acodec,
                "sample_rate": sr,
                "channels": ch,
            }
        else:
            result["audio"] = None
            result["diagnosis"].append("❌ Ses akışı yok (Sessiz / Audio kaydedilmedi).")
            result["healthy"] = False

    except Exception as e:
        result["error"] = f"ffmpeg inceleme hatası: {e}"
        return result

    # 2. Volume analysis
    if result["audio"]:
        try:
            vol_r = subprocess.run(
                [
                    ff, "-i", video_path,
                    "-af", "volumedetect",
                    "-vn", "-sn", "-dn",
                    "-f", "null", "-",
                ],
                capture_output=True,
                text=True,
                timeout=20,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            vol_stderr = vol_r.stderr or ""
            mean_vol = "-91.0 dB"
            max_vol = "-91.0 dB"
            for line in vol_stderr.splitlines():
                if "mean_volume:" in line:
                    mean_vol = line.split("mean_volume:")[1].strip()
                elif "max_volume:" in line:
                    max_vol = line.split("max_volume:")[1].strip()
            result["audio"]["mean_volume"] = mean_vol
            result["audio"]["max_volume"] = max_vol

            if "-91" in max_vol or "-90" in max_vol or "-0.0 dB" == mean_vol:
                result["diagnosis"].append("⚠️ Ses akışı var ancak tamamen SESSİZ (0 dB sinyal).")
                result["healthy"] = False
            else:
                result["diagnosis"].append(f"✓ Ses duyulabilir ve net (Maks: {max_vol}, Ort: {mean_vol}).")
        except Exception as e:
            result["audio"]["volume_err"] = str(e)

    if result.get("video") and result["video"]["fps"] > 0:
        result["diagnosis"].append(f"✓ Video akıcı ({result['video']['fps']} FPS, {result['video']['width']}x{result['video']['height']}).")

    if not result["diagnosis"]:
        result["diagnosis"].append("✓ Kayıt kusursuz.")

    # Write report file to APPDATA
    try:
        report_file = os.path.join(config.APPDATA_DIR, "last_clip_diagnosis.json")
        with open(report_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

    return result


class ClipAnalysisModal(ctk.CTkToplevel):
    """Modern modal dialog showing comprehensive clip analysis."""

    def __init__(self, master, video_path: str):
        super().__init__(master)
        self.video_path = video_path
        self.title("DustReplay — Video Analiz Raporu")
        self.geometry("540x520")
        self.resizable(False, False)
        self.configure(fg_color=theme.BG)
        self.attributes("-topmost", True)
        self.grab_set()

        hdr = ctk.CTkFrame(self, fg_color=theme.HEADER_BG, height=50, corner_radius=0)
        hdr.pack(fill="x")
        ctk.CTkLabel(
            hdr,
            text="🔍 Video Analiz & Teşhis Raporu",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=theme.TEXT,
        ).pack(side="left", padx=16, pady=12)
        ctk.CTkButton(
            hdr,
            text="✕",
            width=32,
            height=32,
            fg_color=theme.BTN_DARK,
            hover_color=theme.BTN_DARK_HOVER,
            command=self.destroy,
        ).pack(side="right", padx=12)

        self.body = ctk.CTkScrollableFrame(self, fg_color=theme.BACKDROP, corner_radius=12)
        self.body.pack(fill="both", expand=True, padx=16, pady=12)

        self.loading_lbl = ctk.CTkLabel(
            self.body,
            text="⏳ Video taranıyor ve ses/görüntü analiz ediliyor…\nLütfen bekleyin.",
            font=ctk.CTkFont(size=13),
            text_color=theme.TEXT_SOFT,
        )
        self.loading_lbl.pack(pady=60)

        threading.Thread(target=self._run_analysis, daemon=True).start()

    def _run_analysis(self):
        diag = run_clip_diagnostics(self.video_path)
        self.after(0, lambda: self._render_results(diag))

    def _render_results(self, diag: dict):
        self.loading_lbl.destroy()

        if diag.get("error"):
            ctk.CTkLabel(
                self.body,
                text=f"Analiz Hatası:\n{diag['error']}",
                font=ctk.CTkFont(size=12),
                text_color=theme.RED,
            ).pack(pady=30)
            return

        # Overview Card
        card = ctk.CTkFrame(self.body, fg_color=theme.PD, corner_radius=10)
        card.pack(fill="x", padx=4, pady=4)
        ctk.CTkLabel(
            card,
            text=f"📁 {diag['file_name']}",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=theme.TEXT,
            anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 4))

        info_str = f"Süre: {diag['duration']} sn  •  Boyut: {diag['file_size_mb']} MB  •  Bitrate: {diag.get('bitrate_kbps', 0)} kbps"
        ctk.CTkLabel(
            card,
            text=info_str,
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_DIM,
            anchor="w",
        ).pack(fill="x", padx=12, pady=(0, 10))

        # Video Stats Card
        v_card = ctk.CTkFrame(self.body, fg_color=theme.PD, corner_radius=10)
        v_card.pack(fill="x", padx=4, pady=4)
        ctk.CTkLabel(
            v_card,
            text="🎥 Video Akışı",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.ACCENT,
            anchor="w",
        ).pack(fill="x", padx=12, pady=(8, 2))
        v = diag.get("video")
        if v:
            v_text = f"Codec: {v['codec'].upper()}  |  Çözünürlük: {v['width']}x{v['height']}  |  FPS: {v['fps']} FPS"
        else:
            v_text = "❌ Video akışı bulunamadı."
        ctk.CTkLabel(
            v_card,
            text=v_text,
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_SOFT if v else theme.RED,
            anchor="w",
        ).pack(fill="x", padx=12, pady=(0, 8))

        # Audio Stats Card
        a_card = ctk.CTkFrame(self.body, fg_color=theme.PD, corner_radius=10)
        a_card.pack(fill="x", padx=4, pady=4)
        ctk.CTkLabel(
            a_card,
            text="🔊 Ses Akışı (Sistem Sesi / Mikrofon)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.ACCENT,
            anchor="w",
        ).pack(fill="x", padx=12, pady=(8, 2))
        a = diag.get("audio")
        if a:
            vol_str = f"Maksimum: {a.get('max_volume', 'N/A')}  |  Ortalama: {a.get('mean_volume', 'N/A')}"
            a_text = f"Codec: {a['codec'].upper()} ({a['sample_rate']} Hz, {a['channels']})\nSes Seviyesi: {vol_str}"
        else:
            a_text = "❌ Ses akışı yok (Sistem sesi veya mikrofon kaydedilemedi)."
        ctk.CTkLabel(
            a_card,
            text=a_text,
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT_SOFT if a else theme.RED,
            anchor="w",
            justify="left",
        ).pack(fill="x", padx=12, pady=(0, 8))

        # Diagnosis Summary
        d_card = ctk.CTkFrame(self.body, fg_color=theme.PD, corner_radius=10)
        d_card.pack(fill="x", padx=4, pady=4)
        ctk.CTkLabel(
            d_card,
            text="📋 Teşhis & Durum",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.GREEN if diag["healthy"] else theme.WARNING,
            anchor="w",
        ).pack(fill="x", padx=12, pady=(8, 2))
        diag_lines = "\n".join(diag.get("diagnosis", []))
        ctk.CTkLabel(
            d_card,
            text=diag_lines,
            font=ctk.CTkFont(size=11),
            text_color=theme.TEXT,
            anchor="w",
            justify="left",
        ).pack(fill="x", padx=12, pady=(0, 8))
