using System.Diagnostics;
using System.Text;

namespace DustReplay.Core;

public sealed class ReplaySaver
{
    public void SaveAsync(
        RecorderService recorder,
        AppSettings settings,
        Action<string>? onDone,
        Action<string>? onError,
        WatchdogService? watchdog = null)
    {
        _ = Task.Run(() =>
        {
            try
            {
                watchdog?.SetPaused(true);
                // Does NOT stop ffmpeg — buffer keeps running 24/7.
                var segs = recorder.GetClosedSegmentsForExport(settings.BufferMinutes);
                watchdog?.SetPaused(false);

                if (segs.Count == 0)
                {
                    var any = Directory.GetFiles(AppPaths.TempDir, "seg_*.mp4").Length;
                    onError?.Invoke(any == 0
                        ? "Recording has not started yet."
                        : "Wait for the first segment to finish, then try again.");
                    return;
                }

                var ff = AppPaths.ResolveFfmpeg();
                if (ff == null)
                {
                    onError?.Invoke("ffmpeg not found.");
                    return;
                }

                Directory.CreateDirectory(settings.EffectiveOutputDir);
                var ts = DateTime.Now.ToString("yyyy-MM-dd_HH-mm-ss");
                var outPath = Path.Combine(settings.EffectiveOutputDir, $"replay_{ts}.mp4");
                var listPath = Path.Combine(settings.EffectiveOutputDir, $"_concat_{ts}.txt");

                var sb = new StringBuilder();
                foreach (var s in segs)
                    sb.AppendLine($"file '{s.Replace('\\', '/')}'");
                File.WriteAllText(listPath, sb.ToString(), Encoding.UTF8);

                if (!MergeExport(ff, listPath, outPath, settings))
                {
                    onError?.Invoke("Merge failed. See app.log / ffmpeg_stderr.log.");
                    try { File.Delete(listPath); } catch { }
                    return;
                }

                try { File.Delete(listPath); } catch { }
                // Do not delete segment files still in rolling buffer window — only exported copies if desired.
                // Python deleted them; we keep buffer segments for continuity.
                onDone?.Invoke(outPath);
            }
            catch (Exception ex)
            {
                watchdog?.SetPaused(false);
                onError?.Invoke(ex.Message);
            }
        });
    }

    private static bool MergeExport(string ff, string listPath, string outPath, AppSettings s)
    {
        var nvenc = EncodingHelper.UseNvenc(ff);
        var venc = EncodingHelper.VideoEncodeArgs(nvenc, s.Quality);
        var abr = $"{Math.Clamp(s.AudioBitrateK, 64, 320)}k";

        bool Run(string args)
        {
            var psi = new ProcessStartInfo(ff, args)
            {
                UseShellExecute = false,
                CreateNoWindow = true,
                RedirectStandardError = true,
            };
            using var p = Process.Start(psi);
            if (p == null) return false;
            p.WaitForExit(900_000);
            return p.ExitCode == 0;
        }

        var copyArgs = $"-y -f concat -safe 0 -i \"{listPath}\" -c copy -movflags +faststart \"{outPath}\"";
        if (Run(copyArgs)) return true;

        var reenc = $"-y -f concat -safe 0 -i \"{listPath}\" {string.Join(" ", venc)} -c:a aac -b:a {abr} -movflags +faststart \"{outPath}\"";
        return Run(reenc);
    }
}
