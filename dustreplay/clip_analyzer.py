"""DustReplay — Clip Analysis Engine & Diagnostics UI.

Analyzes recorded MP4 clips for video FPS stability, audio tracks, volume dB levels,
A/V synchronization, and generates diagnosis reports for user and debugging.
"""

import json
import logging
import os
import subprocess
import threading
import customtkinter as ctk
import config
import theme
import i18n

logger = logging.getLogger(__name__)


def run_clip_diagnostics(video_path: str) -> dict:
    """Analyze video file using ffprobe and ffmpeg volumedetect."""
    if not os.path.isfile(video_path):
        return {"error": f"File not found: {video_path}"}

    ff = config.resolve_ffmpeg_exe() or "ffmpeg"
    ffprobe = os.path.join(os.path.dirname(ff), "ffprobe.exe") if os.path.isfile(os.path.join(os.path.dirname(ff), "ffprobe.exe")) else "ffprobe"

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

    # 1. ffprobe analysis
    try:
        r = subprocess.run(
            [
                ffprobe, "-v", "error",
                "-show_streams", "-show_format",
                "-of", "json",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        data = json.loads(r.stdout)
        fmt = data.get("format", {})
        result["duration"] = round(float(fmt.get("duration", 0)), 2)
        result["bitrate_kbps"] = int(float(fmt.get("bit_rate", 0)) / 1000) if fmt.get("bit_rate") else 0

        streams = data.get("streams", [])
        v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        if v_stream:
            fps_raw = v_stream.get("avg_frame_rate", "0/1").split("/")
            fps = float(fps_raw[0]) / float(fps_raw[1]) if len(fps_raw) == 2 and float(fps_raw[1]) != 0 else 0
            v_start = float(v_stream.get("start_time", 0))
            result["video"] = {
                "codec": v_stream.get("codec_name", "unknown"),
                "width": v_stream.get("width", 0),
                "height": v_stream.get("height", 0),
                "fps": round(fps, 1),
                "start_time": v_start,
            }
        else:
            result["video"] = None
            result["diagnosis"].append("❌ Video akışı bulunamadı.")
            result["healthy"] = False

        if a_stream:
            a_start = float(a_stream.get("start_time", 0))
            result["audio"] = {
                "codec": a_stream.get("codec_name", "unknown"),
                "sample_rate": a_stream.get("sample_rate", "unknown"),
                "channels": a_stream.get("channels", 0),
                "channel_layout": a_stream.get("channel_layout", "unknown"),
                "start_time": a_start,
            }
            if v_stream:
                offset = abs(v_start - a_start) * 1000
                result["sync_offset_ms"] = round(offset, 1)
                if offset > 150:
                    result["diagnosis"].append(f"⚠️ Ses-Görüntü senkron kayması: {offset:.1f} ms")
                    result["healthy"] = False
        else:
            result["audio"] = None
            result["diagnosis"].append("❌ Ses akışı yok (Sessiz / Audio yakalanamadı).")
            result["healthy"] = False

    except Exception as e:
        result["error"] = f"ffprobe hatası: {e}"
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

            if "-91" in max_vol or "-90" in max_vol:
                result["diagnosis"].append("⚠️ Ses parçası mevcut ancak tamamen SESSİZ (0 dB dalga boyu).")
                result["healthy"] = False
            else:
                result["diagnosis"].append(f"✓ Ses aktif ve duyulabilir seviyede (Maksimum: {max_vol}).")
        except Exception as e:
            result["audio"]["volume_err"] = str(e)

    if v_stream and result["video"]["fps"] > 0:
        result["diagnosis"].append(f"✓ Video akıcı kaydedilmiş ({result['video']['fps']} FPS, {result['video']['width']}x{result['video']['height']}).")

    if not result["diagnosis"]:
        result["diagnosis"].append("✓ Kayıt kusursuz görünüyor.")

    # Write report file to APPDATA for persistence
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

        # Title
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
            text="🔊 Ses Akışı (WASAPI / Mikrofon)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=theme.ACCENT,
            anchor="w",
        ).pack(fill="x", padx=12, pady=(8, 2))
        a = diag.get("audio")
        if a:
            vol_str = f"Maksimum: {a.get('max_volume', 'N/A')}  |  Ortalama: {a.get('mean_volume', 'N/A')}"
            a_text = f"Codec: {a['codec'].upper()} ({a['sample_rate']} Hz, {a['channels']} Kanal)\nSes Seviyesi: {vol_str}\nA/V Senkron Kayması: {diag['sync_offset_ms']} ms"
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
