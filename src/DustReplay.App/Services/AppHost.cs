using System.IO;
using System.Windows;
using DustReplay.App.UI;
using DustReplay.Core;

namespace DustReplay.App.Services;

public sealed class AppHost
{
    private readonly SingleInstanceMutex _mutex = new();
    private AppSettings _settings = null!;
    private RecorderService _recorder = null!;
    private WatchdogService _watchdog = null!;
    private readonly ReplaySaver _saver = new();
    private TrayService? _tray;
    private SidePanelWindow? _sidePanel;
    private MainAppWindow? _mainWindow;
    private OverlayWindow? _overlay;
    private HotkeyService? _hotkeys;

    public AppSettings Settings => _settings;
    public RecorderService Recorder => _recorder;
    public bool IsRecording { get; private set; } = true;

    public void Start()
    {
        if (!_mutex.TryAcquire())
        {
            MessageBox.Show("DustReplay is already running.", AppPaths.DisplayName);
            Shutdown();
            return;
        }

        AppPaths.EnsureDirs();
        _settings = AppSettings.Load();
        _recorder = new RecorderService(_settings);
        _watchdog = new WatchdogService(_recorder, _settings, (t, m) => _tray?.Notify(t, m));

        try
        {
            _recorder.Start();
            _watchdog.Start();
        }
        catch (Exception ex)
        {
            MessageBox.Show(ex.Message, AppPaths.DisplayName, MessageBoxButton.OK, MessageBoxImage.Error);
            Shutdown();
            return;
        }

        _tray = new TrayService(this);
        _sidePanel = new SidePanelWindow(this);
        _mainWindow = new MainAppWindow(this);
        _overlay = new OverlayWindow(_settings);
        if (_settings.OverlayEnabled) _overlay.ShowDot();

        _hotkeys = new HotkeyService(_settings);
        _hotkeys.RegisterSave(() => SaveReplay());
        _hotkeys.RegisterToggle(() => ToggleCapture());
        _hotkeys.RegisterPanel(() => Application.Current.Dispatcher.Invoke(ToggleSidePanel));
    }

    public void ToggleSidePanel()
    {
        Application.Current.Dispatcher.Invoke(() =>
        {
            if (_sidePanel == null) return;
            if (_sidePanel.IsVisible) _sidePanel.Hide();
            else _sidePanel.ShowAndFocus();
        });
    }

    public void ToggleMainWindow()
    {
        Application.Current.Dispatcher.Invoke(() =>
        {
            if (_mainWindow == null) return;
            if (_mainWindow.IsVisible) _mainWindow.Hide();
            else _mainWindow.ShowAndFocus();
        });
    }

    public void SaveReplay()
    {
        _saver.SaveAsync(_recorder, _settings,
            path => Application.Current.Dispatcher.Invoke(() =>
            {
                _tray?.Notify(AppPaths.DisplayName, $"Saved: {Path.GetFileName(path)}");
                _mainWindow?.RefreshGallery();
            }),
            err => Application.Current.Dispatcher.Invoke(() =>
                MessageBox.Show(err, AppPaths.DisplayName)));
    }

    public void ToggleCapture()
    {
        if (IsRecording)
        {
            _recorder.Stop();
            _watchdog.Stop();
            IsRecording = false;
        }
        else
        {
            _recorder.Start();
            _watchdog.Start();
            IsRecording = true;
        }
        _sidePanel?.RefreshState();
        _mainWindow?.RefreshState();
        _tray?.UpdateIcon(IsRecording);
    }

    public void ApplySettings(AppSettings s)
    {
        _settings = s;
        s.Save();
        _recorder.UpdateSettings(s);
        _overlay?.ApplySettings(s);
        if (IsRecording)
        {
            _recorder.Restart();
        }
        _hotkeys?.Rebind(s);
    }

    public void Shutdown()
    {
        _hotkeys?.Dispose();
        _overlay?.Close();
        _sidePanel?.Close();
        _mainWindow?.Close();
        _tray?.Dispose();
        _watchdog.Dispose();
        _recorder.Dispose();
        _mutex.Release();
        Application.Current.Shutdown();
    }
}
