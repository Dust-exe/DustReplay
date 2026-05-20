using System.Drawing;
using System.IO;
using System.Windows;
using DustReplay.App.Branding;
using Hardcodet.Wpf.TaskbarNotification;

namespace DustReplay.App.Services;

public sealed class TrayService : IDisposable
{
    private readonly AppHost _host;
    private readonly TaskbarIcon _icon;

    public TrayService(AppHost host)
    {
        _host = host;
        _icon = new TaskbarIcon
        {
            ToolTipText = "DustReplay",
            ContextMenu = BuildMenu(),
        };
        UpdateIcon(true);
        _icon.TrayLeftMouseUp += (_, _) => _host.ToggleMainWindow();
    }

    private System.Windows.Controls.ContextMenu BuildMenu()
    {
        var m = new System.Windows.Controls.ContextMenu();
        m.Items.Add(Mk("Open DustReplay", () => _host.ToggleMainWindow()));
        m.Items.Add(Mk("Panel (Alt+C)", () => _host.ToggleSidePanel()));
        m.Items.Add(new System.Windows.Controls.Separator());
        m.Items.Add(Mk("Save replay", () => _host.SaveReplay()));
        m.Items.Add(Mk("Pause / resume capture", () => _host.ToggleCapture()));
        m.Items.Add(new System.Windows.Controls.Separator());
        m.Items.Add(Mk("Quit", () => _host.Shutdown()));
        return m;
    }

    private static System.Windows.Controls.MenuItem Mk(string text, Action act)
    {
        var i = new System.Windows.Controls.MenuItem { Header = text };
        i.Click += (_, _) => act();
        return i;
    }

    public void UpdateIcon(bool recording)
    {
        try
        {
            if (File.Exists(BrandingPaths.LogoPath))
            {
                using var src = new Bitmap(BrandingPaths.LogoPath);
                using var bmp = new Bitmap(32, 32);
                using var g = Graphics.FromImage(bmp);
                g.Clear(Color.FromArgb(20, 16, 28));
                g.DrawImage(src, 2, 2, 28, 28);
                _icon.Icon = Icon.FromHandle(bmp.GetHicon());
                return;
            }
        }
        catch { /* fallback */ }
        using var fb = new Bitmap(32, 32);
        using var fg = Graphics.FromImage(fb);
        fg.Clear(Color.FromArgb(20, 16, 28));
        using var brush = new SolidBrush(recording ? Color.FromArgb(139, 108, 240) : Color.Gray);
        fg.FillEllipse(brush, 6, 6, 20, 20);
        _icon.Icon = Icon.FromHandle(fb.GetHicon());
    }

    public void Notify(string title, string message) =>
        _icon.ShowBalloonTip(title, message, BalloonIcon.Info);

    public void Dispose() => _icon.Dispose();
}
