namespace DustReplay.Core;

/// <summary>Builds ffmpeg command lines for rolling buffer and export.</summary>
public static class FfmpegCommandBuilder
{
    public static string BuildBufferCommand(string ffmpeg, AppSettings s)
    {
        var pat = Path.Combine(AppPaths.TempDir, "seg_%Y%m%d_%H%M%S.mp4");
        var fps = s.Fps.ToString();
        var encoder = EncodingHelper.ResolveEncoder(ffmpeg);
        var venc = string.Join(" ", EncodingHelper.VideoEncodeArgs(encoder, s.Quality));
        var ddaIdx = Math.Max(0, s.MonitorIndex - 1);
        var scale = CaptureScaleFilter(s);
        var flip = CaptureFlipSuffix(s.CaptureFlip);
        var abr = $"{Math.Clamp(s.AudioBitrateK, 64, 320)}k";

        var videoSrc = s.CaptureBackend.Equals("gdigrab", StringComparison.OrdinalIgnoreCase)
            ? BuildGdigrabSource(fps, ddaIdx)
            : BuildDdagrabSource(fps, ddaIdx);

        var audioParts = BuildAudioInputs(ffmpeg, s);
        var n = audioParts.Count;

        var vconv = $"{videoSrc},fps={fps},{scale}{flip},format=yuv420p[vout]";
        var fc = n switch
        {
            2 => $"{vconv};[0:a]aresample=48000[a0];[1:a]aresample=48000[a1];[a0][a1]amix=inputs=2:duration=longest[aout]",
            1 => $"{vconv};[0:a]aresample=48000[aout]",
            _ => vconv,
        };

        var args = new List<string> { "-y" };
        foreach (var a in audioParts) args.AddRange(a);
        args.AddRange(["-filter_complex", fc]);
        if (n >= 1)
        {
            args.AddRange(["-map", "[vout]", "-map", "[aout]", .. EncodingHelper.VideoEncodeArgs(encoder, s.Quality),
                "-c:a", "aac", "-b:a", abr]);
        }
        else
        {
            args.AddRange(["-map", "[vout]", .. EncodingHelper.VideoEncodeArgs(encoder, s.Quality)]);
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

    private static string BuildDdagrabSource(string fps, int outputIdx) =>
        $"ddagrab=output_idx={outputIdx}:draw_mouse=1:framerate={fps},hwdownload,format=bgra";

    private static string BuildGdigrabSource(string fps, int monitorIdx)
    {
        // Desktop capture — often more stable in exclusive-fullscreen games than DDA.
        return $"gdigrab=framerate={fps}:draw_mouse=1:desktop=1,format=bgra";
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
        // Simplified: WASAPI loopback + optional dshow mic via ffmpeg device list would need probe.
        // For MVP use same sentinel as Python — full device UI in settings later.
        if (!string.IsNullOrEmpty(s.MicDevice) && s.MicDevice != "__wasapi_in__")
            list.Add(["-thread_queue_size", "4096", "-f", "dshow", "-i", $"audio={s.MicDevice}"]);
        if (s.SysAudioDevice == "__wasapi_out__")
            list.Add(["-thread_queue_size", "2048", "-f", "wasapi", "-loopback", "-i", "default"]);
        else if (!string.IsNullOrEmpty(s.SysAudioDevice))
            list.Add(["-thread_queue_size", "4096", "-f", "dshow", "-i", $"audio={s.SysAudioDevice}"]);
        return list;
    }

    private static string EscapeArg(string a) =>
        a.Contains(' ') ? $"\"{a.Replace("\"", "\\\"")}\"" : a;
}
