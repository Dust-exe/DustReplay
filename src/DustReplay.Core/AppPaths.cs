namespace DustReplay.Core;

public static class AppPaths
{
    public const string AppName = "DustReplay";
    public const string DisplayName = "DustReplay";
    public const string MutexName = "DustReplayMutex_v2";

    public static string AppData =>
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData), AppName);

    public static string TempDir => Path.Combine(AppData, "temp");
    public static string SettingsFile => Path.Combine(AppData, "settings.json");
    public static string LogDir => AppData;
    public static string FfmpegStderrLog => Path.Combine(AppData, "ffmpeg_stderr.log");
    public static string AppLog => Path.Combine(AppData, "app.log");
    public static string FfmpegPidFile => Path.Combine(AppData, "ffmpeg.pid");

    public static string DefaultOutputDir =>
        Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyVideos), AppName);

    public static void EnsureDirs()
    {
        Directory.CreateDirectory(AppData);
        Directory.CreateDirectory(TempDir);
        Directory.CreateDirectory(DefaultOutputDir);
    }

    public static IEnumerable<string> FfmpegCandidates()
    {
        var baseDir = AppContext.BaseDirectory;
        yield return Path.Combine(baseDir, "ffmpeg", "ffmpeg.exe");
        yield return Path.Combine(AppData, "ffmpeg", "ffmpeg.exe");
    }

    public static string? ResolveFfmpeg()
    {
        foreach (var p in FfmpegCandidates())
        {
            if (File.Exists(p)) return p;
        }
        return null;
    }
}
