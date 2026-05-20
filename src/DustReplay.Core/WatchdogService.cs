namespace DustReplay.Core;

/// <summary>
/// Monitors buffer process health. Restarts only when ffmpeg actually died (not on a fixed segment schedule).
/// </summary>
public sealed class WatchdogService : IDisposable
{
    private readonly RecorderService _recorder;
    private readonly AppSettings _settings;
    private readonly Action<string, string>? _notify;
    private CancellationTokenSource? _cts;
    private int _crashCount;
    private volatile bool _paused;

    public WatchdogService(RecorderService recorder, AppSettings settings, Action<string, string>? notify = null)
    {
        _recorder = recorder;
        _settings = settings;
        _notify = notify;
    }

    public void SetPaused(bool paused) => _paused = paused;

    public void Start()
    {
        _cts = new CancellationTokenSource();
        _ = LoopAsync(_cts.Token);
    }

    public void Stop() => _cts?.Cancel();

    private async Task LoopAsync(CancellationToken ct)
    {
        var interval = TimeSpan.FromSeconds(Math.Max(1, _settings.WatchdogIntervalSec));
        var delay = TimeSpan.FromSeconds(Math.Max(1, _settings.CrashRestartDelaySec));

        while (!ct.IsCancellationRequested)
        {
            await Task.Delay(interval, ct);
            if (_paused) continue;

            if (_recorder.BufferAlive)
            {
                if (_crashCount > 0) _crashCount = Math.Max(0, _crashCount - 1);
                continue;
            }

            _crashCount++;
            if (_crashCount >= _settings.MaxCrashCount)
                _notify?.Invoke(AppPaths.DisplayName, $"ffmpeg crashed {_crashCount} times. Check logs.");

            await Task.Delay(delay, ct);
            try
            {
                _recorder.Restart();
            }
            catch (Exception ex)
            {
                _notify?.Invoke(AppPaths.DisplayName, $"Restart failed: {ex.Message}");
            }
        }
    }

    public void Dispose() => _cts?.Cancel();
}
