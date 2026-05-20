using System.Text.Json;
using System.Text.Json.Serialization;

namespace DustReplay.Core;

public sealed class AppSettings
{
    public int BufferMinutes { get; set; } = 10;
    /// <summary>Longer segments = fewer mux boundaries (less glitch in games).</summary>
    public int SegmentSeconds { get; set; } = 30;
    public int Fps { get; set; } = 20;
    public int Quality { get; set; } = 36;
    public int CaptureMaxHeight { get; set; } = 720;
    public int AudioBitrateK { get; set; } = 96;
    public string VideoEncoder { get; set; } = "auto";
    public int MonitorIndex { get; set; } = 1;
    public string CaptureFlip { get; set; } = "none";
    /// <summary>ddagrab (GPU) or gdigrab (better for some fullscreen games).</summary>
    public string CaptureBackend { get; set; } = "ddagrab";
    public string MicDevice { get; set; } = "";
    public string SysAudioDevice { get; set; } = "__wasapi_out__";
    public string HotkeySave { get; set; } = "f9";
    public string HotkeyToggle { get; set; } = "f10";
    public string PanelHotkey { get; set; } = "alt+c";
    public string PanelSide { get; set; } = "right";
    public string OutputDir { get; set; } = "";
    /// <summary>Health check interval — not segment rotation.</summary>
    public int WatchdogIntervalSec { get; set; } = 2;
    public int MaxCrashCount { get; set; } = 10;
    public int CrashRestartDelaySec { get; set; } = 1;
    public int SegmentCleanupGraceSec { get; set; } = 90;
    public bool OverlayEnabled { get; set; } = true;
    public string OverlayCorner { get; set; } = "tr";
    public string UiLanguage { get; set; } = "tr";

    [JsonIgnore]
    public string EffectiveOutputDir =>
        string.IsNullOrWhiteSpace(OutputDir) ? AppPaths.DefaultOutputDir : OutputDir;

    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        WriteIndented = true,
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
    };

    public static AppSettings Load()
    {
        AppPaths.EnsureDirs();
        var s = new AppSettings { OutputDir = AppPaths.DefaultOutputDir };
        if (!File.Exists(AppPaths.SettingsFile)) return Migrate(s);
        try
        {
            var json = File.ReadAllText(AppPaths.SettingsFile);
            var loaded = JsonSerializer.Deserialize<AppSettings>(json, JsonOpts);
            if (loaded != null)
            {
                if (string.IsNullOrWhiteSpace(loaded.OutputDir))
                    loaded.OutputDir = AppPaths.DefaultOutputDir;
                return Migrate(loaded);
            }
        }
        catch { /* use defaults */ }
        return Migrate(s);
    }

    public void Save()
    {
        AppPaths.EnsureDirs();
        File.WriteAllText(AppPaths.SettingsFile, JsonSerializer.Serialize(this, JsonOpts));
    }

    private static AppSettings Migrate(AppSettings s)
    {
        if (s.SegmentSeconds < 15) s.SegmentSeconds = 30;
        if (s.SegmentSeconds > 60) s.SegmentSeconds = 60;
        if (s.Fps > 30) s.Fps = 30;
        if (s.Fps < 10) s.Fps = 10;
        if (s.MonitorIndex < 1) s.MonitorIndex = 1;
        if (s.WatchdogIntervalSec < 1) s.WatchdogIntervalSec = 2;
        if (string.IsNullOrEmpty(s.SysAudioDevice)) s.SysAudioDevice = "__wasapi_out__";
        if (s.CaptureBackend is not ("ddagrab" or "gdigrab"))
            s.CaptureBackend = "ddagrab";
        return s;
    }
}
