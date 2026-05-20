using Microsoft.Win32;

namespace DustReplay.App.Services;

public static class StartupService
{
    private const string RunKey = @"Software\Microsoft\Windows\CurrentVersion\Run";
    private const string ValueName = "DustReplay";

    public static bool IsRegistered()
    {
        try
        {
            using var key = Registry.CurrentUser.OpenSubKey(RunKey, false);
            return key?.GetValue(ValueName) is string;
        }
        catch { return false; }
    }

    public static bool Register()
    {
        try
        {
            var exe = Environment.ProcessPath ?? "";
            if (string.IsNullOrEmpty(exe)) return false;
            using var key = Registry.CurrentUser.OpenSubKey(RunKey, true);
            key?.SetValue(ValueName, $"\"{exe}\"");
            return true;
        }
        catch { return false; }
    }

    public static void Unregister()
    {
        try
        {
            using var key = Registry.CurrentUser.OpenSubKey(RunKey, true);
            key?.DeleteValue(ValueName, false);
        }
        catch { /* ignore */ }
    }
}
