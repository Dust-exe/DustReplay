using System.Diagnostics;

namespace DustReplay.Core;

public static class EncodingHelper
{
    public static bool UseNvenc(string ffmpeg)
    {
        var mode = AppSettings.Load().VideoEncoder.ToLowerInvariant();
        if (mode == "cpu") return false;
        if (mode == "nvenc") return true;
        try
        {
            var psi = new ProcessStartInfo(ffmpeg, "-hide_banner -encoders")
            {
                RedirectStandardOutput = true,
                UseShellExecute = false,
                CreateNoWindow = true,
            };
            using var p = Process.Start(psi);
            if (p == null) return false;
            var o = p.StandardOutput.ReadToEnd();
            p.WaitForExit(5000);
            return o.Contains("h264_nvenc", StringComparison.Ordinal);
        }
        catch
        {
            return false;
        }
    }

    public static string[] VideoEncodeArgs(bool nvenc, int quality)
    {
        var q = Math.Clamp(quality, 18, 51);
        if (nvenc)
            return ["-c:v", "h264_nvenc", "-preset", "p4", "-tune", "hq", "-rc", "vbr", "-cq", q.ToString(), "-b:v", "0"];
        return ["-c:v", "libx264", "-preset", "superfast", "-crf", q.ToString()];
    }
}
