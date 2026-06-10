using System.Diagnostics;

namespace DustReplay.Core;

public enum EncoderType
{
    Cpu,
    Nvenc,
    Amf
}

public static class EncodingHelper
{
    public static EncoderType ResolveEncoder(string ffmpeg)
    {
        var mode = AppSettings.Load().VideoEncoder.ToLowerInvariant();

        if (mode == "cpu" || mode == "libx264" || mode == "x264")
            return EncoderType.Cpu;

        string availableEncoders = string.Empty;
        try
        {
            var psi = new ProcessStartInfo(ffmpeg, "-hide_banner -encoders")
            {
                RedirectStandardOutput = true,
                UseShellExecute = false,
                CreateNoWindow = true,
            };
            using var p = Process.Start(psi);
            if (p != null)
            {
                availableEncoders = p.StandardOutput.ReadToEnd();
                p.WaitForExit(5000);
            }
        }
        catch
        {
            // fallback if ffmpeg check fails
        }

        bool HasEncoder(string encoderName) => availableEncoders.Contains(encoderName, StringComparison.OrdinalIgnoreCase);

        if (mode == "nvenc" || mode == "nvidia" || mode == "gpu" || mode == "h264_nvenc")
            return HasEncoder("h264_nvenc") ? EncoderType.Nvenc : EncoderType.Cpu;

        if (mode == "amf" || mode == "amd" || mode == "h264_amf")
            return HasEncoder("h264_amf") ? EncoderType.Amf : EncoderType.Cpu;

        // Auto mode
        if (HasEncoder("h264_nvenc"))
            return EncoderType.Nvenc;
        if (HasEncoder("h264_amf"))
            return EncoderType.Amf;

        return EncoderType.Cpu;
    }

    public static string[] VideoEncodeArgs(EncoderType encoder, int quality)
    {
        var q = Math.Clamp(quality, 18, 51);

        if (encoder == EncoderType.Nvenc)
            return ["-c:v", "h264_nvenc", "-preset", "p1", "-rc", "constqp", "-qp", q.ToString()];

        if (encoder == EncoderType.Amf)
            return ["-c:v", "h264_amf", "-usage", "ultralowlatency", "-quality", "speed", "-rc", "cqp", "-qp", q.ToString()];

        return ["-c:v", "libx264", "-preset", "ultrafast", "-crf", q.ToString()];
    }
}
