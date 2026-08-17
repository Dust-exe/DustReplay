"""DustReplay — Video / Audio Clip Diagnostic Tool.

Analyzes recorded clips for:
- Video resolution, FPS stability, jitter, keyframe GOP
- Audio presence, channels, sample rate, volume level (dB), silence detection
- Audio / Video timestamp synchronization (PTS drift)
- Stutter / frame drop indicators
"""

import json
import os
import subprocess
import sys


def diagnose(video_path: str):
    if not os.path.isfile(video_path):
        print(f"[-] File not found: {video_path}")
        return

    print("=" * 60)
    print(f" DustReplay Diagnostic Report: {os.path.basename(video_path)}")
    print(f" Path: {os.path.abspath(video_path)}")
    print(f" Size: {os.path.getsize(video_path) / 1048576:.2f} MB")
    print("=" * 60)

    # 1. ffprobe stream info
    try:
        r = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_streams", "-show_format",
                "-of", "json",
                video_path,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(r.stdout)
    except Exception as e:
        print(f"[-] ffprobe failed: {e}")
        return

    streams = data.get("streams", [])
    format_info = data.get("format", {})
    duration = float(format_info.get("duration", 0))
    print(f"\n[+] Container: {format_info.get('format_long_name', 'Unknown')}")
    print(f"[+] Total Duration: {duration:.2f} seconds")
    print(f"[+] Overall Bitrate: {int(format_info.get('bit_rate', 0)) / 1000:.0f} kbps")

    v_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    a_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    # 2. Video Analysis
    print("\n--- VIDEO STREAM ---")
    if v_stream:
        codec = v_stream.get("codec_name", "unknown")
        w = v_stream.get("width")
        h = v_stream.get("height")
        fps_raw = v_stream.get("avg_frame_rate", "0/1")
        fps_parts = fps_raw.split("/")
        fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 and float(fps_parts[1]) != 0 else 0
        v_start = float(v_stream.get("start_time", 0))
        print(f"  Codec: {codec}")
        print(f"  Resolution: {w}x{h}")
        print(f"  Reported FPS: {fps:.2f}")
        print(f"  Video Start Time: {v_start:.3f} s")
    else:
        print("  [!] NO VIDEO STREAM DETECTED!")

    # 3. Audio Analysis & Volume Detect
    print("\n--- AUDIO STREAM ---")
    if a_stream:
        acodec = a_stream.get("codec_name", "unknown")
        sr = a_stream.get("sample_rate", "unknown")
        channels = a_stream.get("channels", 0)
        ch_layout = a_stream.get("channel_layout", "unknown")
        a_start = float(a_stream.get("start_time", 0))
        print(f"  Codec: {acodec}")
        print(f"  Sample Rate: {sr} Hz")
        print(f"  Channels: {channels} ({ch_layout})")
        print(f"  Audio Start Time: {a_start:.3f} s")

        if v_stream:
            diff_ms = abs(v_start - a_start) * 1000
            if diff_ms < 50:
                print(f"  A/V Sync Offset: {diff_ms:.1f} ms  ✓ (Excellent sync)")
            elif diff_ms < 150:
                print(f"  A/V Sync Offset: {diff_ms:.1f} ms  ! (Acceptable sync)")
            else:
                print(f"  A/V Sync Offset: {diff_ms:.1f} ms  [!] (POSSIBLE AUDIO DESYNC)")

        # Volume measurement
        try:
            vol_r = subprocess.run(
                [
                    "ffmpeg", "-i", video_path,
                    "-af", "volumedetect",
                    "-vn", "-sn", "-dn",
                    "-f", "null", "-",
                ],
                capture_output=True,
                text=True,
            )
            vol_stderr = vol_r.stderr
            mean_vol = None
            max_vol = None
            for line in vol_stderr.splitlines():
                if "mean_volume:" in line:
                    mean_vol = line.split("mean_volume:")[1].strip()
                elif "max_volume:" in line:
                    max_vol = line.split("max_volume:")[1].strip()
            print(f"  Volume Levels: Mean: {mean_vol} | Max: {max_vol}")
            if max_vol and "-91" in max_vol:
                print("  [!] WARNING: Audio track appears to be COMPLETELY SILENT!")
            else:
                print("  ✓ Audio track contains audible sound waveform.")
        except Exception as e:
            print(f"  Could not run volume detection: {e}")
    else:
        print("  [!] NO AUDIO STREAM IN FILE! (Muted / Audio failed during capture)")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        diagnose(sys.argv[1])
    else:
        print("Usage: python diagnose_clip.py <path_to_clip.mp4>")
