namespace DustReplay.Core;

/// <summary>Builds ffmpeg command lines for rolling buffer and export.</summary>
public static class FfmpegCommandBuilder
{
    public static string BuildBufferCommand(string ffmpeg, AppSettings s)
    {
        var pat = Path.Combine(AppPaths.TempDir, "seg_%Y%m%d_%H%M%S.mp4");
        var fps = s.Fps.ToString();
        var nvenc = EncodingHelper.UseNvenc(ffmpeg);
        var venc = string.Join(" ", EncodingHelper.VideoEncodeArgs(nvenc, s.Quality));
        var ddaIdx = Math.Max(0, s.MonitorIndex - 1);
        var scale = CaptureScaleFilter(s);
        var flip = CaptureFlipSuffix(s.CaptureFlip);
        var abr = $"{Math.Clamp(s.AudioBitrateK, 64, 320)}k";

        var isGdigrab = s.CaptureBackend.Equals("gdigrab", StringComparison.OrdinalIgnoreCase);

        var args = new List<string> { "-y" };

        // Video input
        args.AddRange(["-thread_queue_size", "4096"]);
        if (isGdigrab)
        {
            args.AddRange(["-f", "gdigrab", "-framerate", fps, "-draw_mouse", "1", "-i", "desktop"]);
        }
        else
        {
            args.AddRange(["-f", "lavfi", "-i", $"ddagrab=output_idx={ddaIdx}:draw_mouse=1:framerate={fps}"]);
        }

        var audioParts = BuildAudioInputs(ffmpeg, s);
        var n = audioParts.Count;
        foreach (var a in audioParts) args.AddRange(a);

        var hwdown = isGdigrab ? "" : "hwdownload,format=bgra,";
        var vconv = $"[0:v]{hwdown}fps={fps},{scale}{flip},format=yuv420p[vout]";

        var fc = n switch
        {
            2 => $"{vconv};[1:a]aresample=async=1:osr=48000[a0];[2:a]aresample=async=1:osr=48000[a1];[a0][a1]amix=inputs=2:duration=longest:dropout_transition=0:normalize=0[aout]",
            1 => $"{vconv};[1:a]aresample=async=1:osr=48000[aout]",
            _ => vconv,
        };

        args.AddRange(["-filter_complex", fc]);
        if (n >= 1)
        {
            args.AddRange(["-map", "[vout]", "-map", "[aout]", .. EncodingHelper.VideoEncodeArgs(nvenc, s.Quality),
                "-c:a", "aac", "-b:a", abr]);
        }
        else
        {
            args.AddRange(["-map", "[vout]", .. EncodingHelper.VideoEncodeArgs(nvenc, s.Quality)]);
        }

        // No -reset_timestamps: avoids black/gap frames at segment boundaries when concatenating.
        args.AddRange([
            "-f", "segment",
            "-segment_time", s.SegmentSeconds.ToString(),
            "-segment_format_options", "flush_packets=1",
            "-strftime", "1",
            pat,
        ]);
        return string.Join(" ", args.Select(EscapeArg));
    }

    private static string CaptureScaleFilter(AppSettings s)
    {
        if (s.CaptureMaxHeight <= 0)
            return "scale=trunc(iw/2)*2:trunc(ih/2)*2";
        var h = Math.Clamp(s.CaptureMaxHeight, 240, 4320);
        return $"scale=trunc(iw*min(1\\,{h}/ih)/2)*2:trunc(min(ih\\,{h})/2)*2";
    }

    private static string CaptureFlipSuffix(string raw)
    {
        raw = (raw ?? "none").ToLowerInvariant();
        return raw switch
        {
            "vertical" or "vflip" => ",vflip",
            "horizontal" or "hflip" => ",hflip",
            "rotate180" or "180" => ",vflip,hflip",
            _ => "",
        };
    }

    private static List<string[]> BuildAudioInputs(string ffmpeg, AppSettings s)
    {
        var list = new List<string[]>();
        if (!string.IsNullOrEmpty(s.MicDevice) && s.MicDevice != "__wasapi_in__")
            list.Add(["-thread_queue_size", "4096", "-f", "dshow", "-i", $"audio={s.MicDevice}"]);
        if (s.SysAudioDevice == "__wasapi_out__")
            list.Add(["-thread_queue_size", "4096", "-f", "wasapi", "-loopback", "1", "-i", "default"]);
        else if (!string.IsNullOrEmpty(s.SysAudioDevice))
            list.Add(["-thread_queue_size", "4096", "-f", "dshow", "-i", $"audio={s.SysAudioDevice}"]);
        return list;
    }

    private static string EscapeArg(string a) =>
        a.Contains(' ') ? $"\"{a.Replace("\"", "\\\"")}\"" : a;
}
