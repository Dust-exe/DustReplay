using System.IO;
using System.Windows;
using System.Windows.Controls;
using DustReplay.App.Services;
using DustReplay.Core;
using Microsoft.Win32;

namespace DustReplay.App.Views;

public partial class SettingsView : UserControl
{
    private readonly AppHost _host;
    private readonly AudioDeviceService _audio = new();
    private List<string> _micValues = new();
    private List<string> _sysValues = new();

    public SettingsView(AppHost host)
    {
        InitializeComponent();
        _host = host;
        BufferSlider.ValueChanged += (_, _) => BufferVal.Text = $"{(int)BufferSlider.Value} dk";
        FpsSlider.ValueChanged += (_, _) => FpsVal.Text = $"{(int)FpsSlider.Value} FPS";
        QualitySlider.ValueChanged += (_, _) => QualityVal.Text = $"{(int)QualitySlider.Value}";
        Loaded += async (_, _) =>
        {
            LoadFromSettings(_host.Settings);
            await LoadAudioAsync();
        };
    }

    private void LoadFromSettings(AppSettings s)
    {
        MonitorBox.Items.Clear();
        for (var i = 1; i <= 4; i++)
            MonitorBox.Items.Add(new ComboBoxItem { Content = $"Ekran #{i}", Tag = i });
        MonitorBox.SelectedIndex = Math.Clamp(s.MonitorIndex - 1, 0, 3);

        FillCombo(FlipBox, [
            ("Normal", "none"), ("Dikey çevir", "vertical"),
            ("Yatay çevir", "horizontal"), ("180°", "rotate180")], s.CaptureFlip);
        FillCombo(EncoderBox, [
            ("Otomatik", "auto"), ("NVENC (GPU)", "nvenc"), ("CPU H.264", "cpu")], s.VideoEncoder);
        BufferSlider.Value = s.BufferMinutes;
        BufferVal.Text = $"{s.BufferMinutes} dk";
        FpsSlider.Value = s.Fps;
        FpsVal.Text = $"{s.Fps} FPS";
        QualitySlider.Value = s.Quality;
        QualityVal.Text = $"{s.Quality}";
        FillCombo(MaxHeightBox, [("720p", "720"), ("1080p", "1080"), ("Native", "0")],
            s.CaptureMaxHeight.ToString());
        FillCombo(CaptureBackendBox, [
            ("ddagrab (GPU)", "ddagrab"), ("gdigrab (oyun)", "gdigrab")], s.CaptureBackend);
        HotkeySaveBox.Text = s.HotkeySave;
        HotkeyToggleBox.Text = s.HotkeyToggle;
        HotkeyPanelBox.Text = s.PanelHotkey;
        FillCombo(PanelSideBox, [("Sağ", "right"), ("Sol", "left")], s.PanelSide);
        OutputDirBox.Text = s.EffectiveOutputDir;
        OverlayEnabledChk.IsChecked = s.OverlayEnabled;
        FillCombo(OverlayCornerBox, [
            ("Sağ üst", "tr"), ("Sol üst", "tl"), ("Sağ alt", "br"), ("Sol alt", "bl")], s.OverlayCorner);
        StatsCpuChk.IsChecked = s.StatsShowCpu;
        StatsRamChk.IsChecked = s.StatsShowRam;
        StatsGpuChk.IsChecked = s.StatsShowGpu;
        StatsFpsChk.IsChecked = s.StatsShowFps;
        FillCombo(StatsModeBox, [
            ("Kompakt", "compact"), ("Normal", "normal"), ("Gelişmiş", "advanced")], s.StatsOverlayMode);
        FillCombo(StatsCornerBox, [
            ("Sağ üst", "tr"), ("Sol üst", "tl"), ("Sağ alt", "br"), ("Sol alt", "bl")], s.StatsOverlayCorner);
        StartupChk.IsChecked = StartupService.IsRegistered();
        LangBox.SelectedIndex = s.UiLanguage == "en" ? 1 : 0;
    }

    private async Task LoadAudioAsync()
    {
        var (micL, micV, sysL, sysV) = await _audio.ListDevicesAsync();
        _micValues = micV;
        _sysValues = sysV;
        MicBox.Items.Clear();
        for (var i = 0; i < micL.Count; i++)
            MicBox.Items.Add(new ComboBoxItem { Content = micL[i], Tag = micV[i] });
        SysBox.Items.Clear();
        for (var i = 0; i < sysL.Count; i++)
            SysBox.Items.Add(new ComboBoxItem { Content = sysL[i], Tag = sysV[i] });
        SelectByTag(MicBox, _host.Settings.MicDevice);
        SelectByTag(SysBox, _host.Settings.SysAudioDevice);
    }

    private static void FillCombo(ComboBox box, (string label, string tag)[] items, string current)
    {
        box.Items.Clear();
        foreach (var (label, tag) in items)
            box.Items.Add(new ComboBoxItem { Content = label, Tag = tag });
        SelectByTag(box, current);
    }

    private static void SelectByTag(ComboBox box, string tag)
    {
        for (var i = 0; i < box.Items.Count; i++)
        {
            if (box.Items[i] is ComboBoxItem item && (item.Tag?.ToString() ?? "") == tag)
            {
                box.SelectedIndex = i;
                return;
            }
        }
        if (box.Items.Count > 0) box.SelectedIndex = 0;
    }

    private static string TagOf(ComboBox box) =>
        (box.SelectedItem as ComboBoxItem)?.Tag?.ToString() ?? "";

    private void BrowseOutput_Click(object sender, RoutedEventArgs e)
    {
        var dlg = new OpenFolderDialog { InitialDirectory = OutputDirBox.Text };
        if (dlg.ShowDialog() == true)
            OutputDirBox.Text = dlg.FolderName;
    }

    private void Save_Click(object sender, RoutedEventArgs e)
    {
        var s = _host.Settings;
        if (MonitorBox.SelectedItem is ComboBoxItem mon && mon.Tag is int idx)
            s.MonitorIndex = idx;
        else
            s.MonitorIndex = MonitorBox.SelectedIndex + 1;

        s.CaptureFlip = TagOf(FlipBox);
        s.VideoEncoder = TagOf(EncoderBox);
        s.BufferMinutes = (int)BufferSlider.Value;
        s.Fps = (int)FpsSlider.Value;
        s.Quality = (int)QualitySlider.Value;
        s.CaptureMaxHeight = int.TryParse(TagOf(MaxHeightBox), out var h) ? h : 720;
        s.CaptureBackend = TagOf(CaptureBackendBox);
        s.MicDevice = TagOf(MicBox);
        s.SysAudioDevice = TagOf(SysBox);
        s.HotkeySave = HotkeySaveBox.Text.Trim().ToLowerInvariant();
        s.HotkeyToggle = HotkeyToggleBox.Text.Trim().ToLowerInvariant();
        s.PanelHotkey = HotkeyPanelBox.Text.Trim().ToLowerInvariant();
        s.PanelSide = TagOf(PanelSideBox);
        s.OutputDir = OutputDirBox.Text.Trim();
        s.OverlayEnabled = OverlayEnabledChk.IsChecked == true;
        s.OverlayCorner = TagOf(OverlayCornerBox);
        s.StatsShowCpu = StatsCpuChk.IsChecked == true;
        s.StatsShowRam = StatsRamChk.IsChecked == true;
        s.StatsShowGpu = StatsGpuChk.IsChecked == true;
        s.StatsShowFps = StatsFpsChk.IsChecked == true;
        s.StatsOverlayMode = TagOf(StatsModeBox);
        s.StatsOverlayCorner = TagOf(StatsCornerBox);
        s.UiLanguage = LangBox.SelectedIndex == 1 ? "en" : "tr";

        if (StartupChk.IsChecked == true)
        {
            if (!StartupService.IsRegistered()) StartupService.Register();
        }
        else
            StartupService.Unregister();

        _host.ApplySettings(s);
        MessageBox.Show("Ayarlar kaydedildi.", AppPaths.DisplayName);
    }
}
