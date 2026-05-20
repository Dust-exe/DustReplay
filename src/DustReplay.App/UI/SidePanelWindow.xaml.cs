using System.Diagnostics;
using System.IO;
using System.Windows;
using System.Windows.Threading;
using DustReplay.App.Services;
using DustReplay.Core;

namespace DustReplay.App.UI;

public partial class SidePanelWindow : Window
{
    private readonly AppHost _host;
    private readonly DispatcherTimer _timer;

    public SidePanelWindow(AppHost host)
    {
        InitializeComponent();
        _host = host;
        VersionText.Text = "v3.3.0";
        _timer = new DispatcherTimer { Interval = TimeSpan.FromSeconds(1) };
        _timer.Tick += (_, _) => RefreshState();
        RefreshState();
    }

    public void ShowAndFocus()
    {
        PositionPanel();
        Show();
        Activate();
        _timer.Start();
    }

    protected override void OnDeactivated(EventArgs e)
    {
        base.OnDeactivated(e);
        Hide();
        _timer.Stop();
    }

    private void PositionPanel()
    {
        var area = SystemParameters.WorkArea;
        Height = area.Height;
        Top = area.Top;
        if (_host.Settings.PanelSide == "left")
        {
            Left = area.Left;
        }
        else
        {
            Left = area.Right - Width;
        }
    }

    public void RefreshState()
    {
        var filled = _host.Recorder.BufferSecondsFilled();
        var max = _host.Settings.BufferMinutes * 60;
        BufferText.Text = $"Buffer: {TimeSpan.FromSeconds(filled):mm\\:ss} / {TimeSpan.FromSeconds(max):mm\\:ss}";
        BufferBar.Value = max > 0 ? Math.Min(100, filled * 100.0 / max) : 0;
        StatusText.Text = $"{_host.Settings.Fps} FPS • {_host.Settings.CaptureBackend} • Ekran #{_host.Settings.MonitorIndex}";
        LiveBadge.Visibility = _host.IsRecording ? Visibility.Visible : Visibility.Collapsed;
    }

    private void Close_Click(object sender, RoutedEventArgs e) => Hide();
    private void Save_Click(object sender, RoutedEventArgs e) => _host.SaveReplay();
    private void Toggle_Click(object sender, RoutedEventArgs e) => _host.ToggleCapture();
    private void OpenFolder_Click(object sender, RoutedEventArgs e)
    {
        var dir = _host.Settings.EffectiveOutputDir;
        Directory.CreateDirectory(dir);
        Process.Start("explorer.exe", dir);
    }
    private void OpenApp_Click(object sender, RoutedEventArgs e) => _host.ToggleMainWindow();
}
