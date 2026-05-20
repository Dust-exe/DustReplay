using System.Diagnostics;

namespace DustReplay.Core;

/// <summary>
/// 24/7 rolling buffer via ffmpeg segment muxer.
/// Save/export does NOT stop capture — only closed segment files are used.
/// </summary>
public sealed class RecorderService : IDisposable
{
    private readonly object _lock = new();
    private Process? _process;
    private AppSettings _settings;
    private CancellationTokenSource? _cleanupCts;
    private bool _running;

    public event Action<string>? Log;
    public event Action? BufferRestarted;

    public RecorderService(AppSettings settings)
    {
        _settings = settings;
        AppPaths.EnsureDirs();
    }

    public bool BufferAlive =>
        _process != null && !_process.HasExited;

    public void UpdateSettings(AppSettings s) => _settings = s;

    public void Start()
    {
        lock (_lock)
        {
            if (_running) return;
            Launch();
            _running = true;
            _cleanupCts = new CancellationTokenSource();
            _ = CleanupLoopAsync(_cleanupCts.Token);
            Log?.Invoke("Recording started.");
        }
    }

    public void Stop()
    {
        lock (_lock)
        {
            if (!_running) return;
            _cleanupCts?.Cancel();
            Terminate();
            _running = false;
            Log?.Invoke("Recording stopped.");
        }
    }

    public void Restart()
    {
        lock (_lock)
        {
            Terminate();
            Thread.Sleep(300);
            Launch();
            BufferRestarted?.Invoke();
            Log?.Invoke("Recording restarted.");
        }
    }

    /// <summary>
    /// Collect finished segments for export without stopping the buffer (no black gaps).
    /// </summary>
    public IReadOnlyList<string> GetClosedSegmentsForExport(int? minutes = null)
    {
        minutes ??= _settings.BufferMinutes;
        var cutoff = DateTime.UtcNow.AddMinutes(-minutes.Value);
        var segDur = TimeSpan.FromSeconds(_settings.SegmentSeconds);
        var segs = Directory.GetFiles(AppPaths.TempDir, "seg_*.mp4")
            .Select(f => new FileInfo(f))
            .OrderBy(f => f.LastWriteTimeUtc)
            .ToList();

        if (segs.Count == 0) return Array.Empty<string>();

        // Last file is usually still being written — exclude if modified recently.
        var last = segs[^1];
        if (DateTime.UtcNow - last.LastWriteTimeUtc < segDur + TimeSpan.FromSeconds(2))
            segs = segs.Take(segs.Count - 1).ToList();

        return segs
            .Where(f => f.LastWriteTimeUtc >= cutoff && f.Length >= 2048)
            .Select(f => f.FullName)
            .ToList();
    }

    public int BufferSecondsFilled()
    {
        var segs = Directory.GetFiles(AppPaths.TempDir, "seg_*.mp4");
        if (segs.Length == 0) return 0;
        var oldest = segs.Min(f => File.GetLastWriteTimeUtc(f));
        return (int)(DateTime.UtcNow - oldest).TotalSeconds;
    }

    public void ResetBuffer()
    {
        foreach (var f in Directory.GetFiles(AppPaths.TempDir, "seg_*.mp4"))
        {
            try { File.Delete(f); } catch { /* ignore */ }
        }
    }

    private void Launch()
    {
        KillStaleFfmpeg();
        var ff = AppPaths.ResolveFfmpeg()
            ?? throw new FileNotFoundException("ffmpeg.exe not found. Reinstall or place under ffmpeg folder.");
        var args = FfmpegCommandBuilder.BuildBufferCommand(ff, _settings);
        Log?.Invoke($"ffmpeg {args}");

        var psi = new ProcessStartInfo(ff, args)
        {
            UseShellExecute = false,
            CreateNoWindow = true,
            RedirectStandardInput = true,
            RedirectStandardError = true,
            WorkingDirectory = AppPaths.TempDir,
        };

        _process = Process.Start(psi);
        if (_process == null) throw new InvalidOperationException("Failed to start ffmpeg.");

        try { File.WriteAllText(AppPaths.FfmpegPidFile, _process.Id.ToString()); } catch { }

        _ = Task.Run(async () =>
        {
            try
            {
                var err = await _process.StandardError.ReadToEndAsync();
                await File.WriteAllTextAsync(AppPaths.FfmpegStderrLog, err);
            }
            catch { /* ignore */ }
        });
    }

    private void Terminate()
    {
        if (_process == null) return;
        try
        {
            if (!_process.HasExited)
            {
                _process.StandardInput.WriteLine("q");
                _process.StandardInput.Flush();
                if (!_process.WaitForExit(8000))
                    _process.Kill(entireProcessTree: true);
            }
        }
        catch
        {
            try { _process.Kill(entireProcessTree: true); } catch { }
        }
        _process = null;
        try { File.Delete(AppPaths.FfmpegPidFile); } catch { }
    }

    private static void KillStaleFfmpeg()
    {
        try
        {
            if (!File.Exists(AppPaths.FfmpegPidFile)) return;
            var pid = int.Parse(File.ReadAllText(AppPaths.FfmpegPidFile).Trim());
            using var p = Process.GetProcessById(pid);
            p.Kill(entireProcessTree: true);
        }
        catch { /* ignore */ }
        try { File.Delete(AppPaths.FfmpegPidFile); } catch { }
    }

    private async Task CleanupLoopAsync(CancellationToken ct)
    {
        while (!ct.IsCancellationRequested)
        {
            try
            {
                var grace = _settings.SegmentCleanupGraceSec;
                var cutoff = DateTime.UtcNow.AddSeconds(-(_settings.BufferMinutes * 60 + grace));
                foreach (var f in Directory.GetFiles(AppPaths.TempDir, "seg_*.mp4"))
                {
                    if (File.GetLastWriteTimeUtc(f) < cutoff)
                    {
                        try { File.Delete(f); } catch { }
                    }
                }
            }
            catch { /* ignore */ }
            await Task.Delay(15000, ct);
        }
    }

    public void Dispose()
    {
        Stop();
        _cleanupCts?.Dispose();
    }
}
