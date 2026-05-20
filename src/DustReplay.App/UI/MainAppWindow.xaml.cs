using System.Diagnostics;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using DustReplay.App.Services;
using DustReplay.Core;

namespace DustReplay.App.UI;

public partial class MainAppWindow : Window
{
    private readonly AppHost _host;

    public MainAppWindow(AppHost host)
    {
        InitializeComponent();
        _host = host;
        LoadSettingsUi();
        RefreshGallery();
        Hide();
    }

    public void ShowAndFocus()
    {
        Show();
        Activate();
        RefreshGallery();
        RefreshState();
    }

    public void RefreshState() { /* bound in side panel */ }

    public void RefreshGallery()
    {
        GalleryItems.Items.Clear();
        var dir = _host.Settings.EffectiveOutputDir;
        if (!Directory.Exists(dir)) return;
        foreach (var f in Directory.GetFiles(dir, "*.mp4").OrderByDescending(File.GetLastWriteTime))
        {
            var card = new Border
            {
                Width = 220,
                Margin = new Thickness(8),
                Background = new SolidColorBrush(Color.FromRgb(20, 16, 32)),
                CornerRadius = new CornerRadius(12),
                BorderBrush = new SolidColorBrush(Color.FromRgb(75, 55, 136)),
                BorderThickness = new Thickness(1),
                Child = BuildCard(f),
            };
            GalleryItems.Items.Add(card);
        }
    }

    private UIElement BuildCard(string path)
    {
        var sp = new StackPanel { Margin = new Thickness(10) };
        var thumb = new Border
        {
            Height = 120,
            Background = new SolidColorBrush(Color.FromRgb(8, 6, 14)),
            CornerRadius = new CornerRadius(8),
            Child = new Grid(),
        };
        var grid = (Grid)thumb.Child;
        var play = new System.Windows.Shapes.Ellipse
        {
            Width = 44, Height = 44,
            Fill = Brushes.White,
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
        };
        grid.Children.Add(play);
        TryLoadThumb(grid, path);
        sp.Children.Add(thumb);
        sp.Children.Add(new TextBlock
        {
            Text = Path.GetFileName(path),
            Foreground = (Brush)FindResource("TextBrush"),
            FontWeight = FontWeights.SemiBold,
            Margin = new Thickness(0, 8, 0, 0),
            TextTrimming = TextTrimming.CharacterEllipsis,
        });
        var row = new StackPanel { Orientation = Orientation.Horizontal, Margin = new Thickness(0, 8, 0, 0) };
        var playBtn = new Button { Content = "Oynat", Style = (Style)FindResource("GhostButton") };
        playBtn.Click += (_, _) => Process.Start(new ProcessStartInfo(path) { UseShellExecute = true });
        row.Children.Add(playBtn);
        sp.Children.Add(row);
        return sp;
    }

    private static void TryLoadThumb(Grid grid, string videoPath)
    {
        var thumbDir = Path.Combine(AppPaths.AppData, "thumbs");
        Directory.CreateDirectory(thumbDir);
        var jpg = Path.Combine(thumbDir, Path.GetFileNameWithoutExtension(videoPath) + ".jpg");
        if (!File.Exists(jpg))
        {
            var ff = AppPaths.ResolveFfmpeg();
            if (ff == null) return;
            try
            {
                Process.Start(new ProcessStartInfo(ff,
                    $"-y -ss 0.35 -i \"{videoPath}\" -vframes 1 -vf scale=280:-1 \"{jpg}\"")
                {
                    CreateNoWindow = true,
                    UseShellExecute = false,
                })?.WaitForExit(8000);
            }
            catch { return; }
        }
        if (!File.Exists(jpg)) return;
        try
        {
            var bmp = new BitmapImage();
            bmp.BeginInit();
            bmp.CacheOption = BitmapCacheOption.OnLoad;
            bmp.UriSource = new Uri(jpg);
            bmp.EndInit();
            var img = new Image
            {
                Source = bmp,
                Stretch = Stretch.UniformToFill,
                Opacity = 0.5,
            };
            grid.Children.Insert(0, img);
        }
        catch { /* ignore */ }
    }

    private void LoadSettingsUi()
    {
        var s = _host.Settings;
        FpsSlider.Value = s.Fps;
        BufferSlider.Value = s.BufferMinutes;
        SelectCombo(CaptureBackendBox, s.CaptureBackend);
        SelectCombo(MaxHeightBox, s.CaptureMaxHeight.ToString());
        SelectCombo(OverlayCornerBox, s.OverlayCorner);
    }

    private static void SelectCombo(ComboBox box, string tag)
    {
        foreach (ComboBoxItem item in box.Items)
        {
            if ((item.Tag?.ToString() ?? "") == tag)
            {
                box.SelectedItem = item;
                return;
            }
        }
        if (box.Items.Count > 0) box.SelectedIndex = 0;
    }

    private void Nav_Click(object sender, RoutedEventArgs e)
    {
        var tag = (string)((Button)sender).Tag;
        PageGallery.Visibility = tag == "gallery" ? Visibility.Visible : Visibility.Collapsed;
        PageSettings.Visibility = tag == "settings" ? Visibility.Visible : Visibility.Collapsed;
    }

    private void Save_Click(object sender, RoutedEventArgs e) => _host.SaveReplay();
    private void Toggle_Click(object sender, RoutedEventArgs e) => _host.ToggleCapture();
    private void RefreshGallery_Click(object sender, RoutedEventArgs e) => RefreshGallery();
    private void OpenFolder_Click(object sender, RoutedEventArgs e)
    {
        var d = _host.Settings.EffectiveOutputDir;
        Directory.CreateDirectory(d);
        Process.Start("explorer.exe", d);
    }

    private void SaveSettings_Click(object sender, RoutedEventArgs e)
    {
        var s = _host.Settings;
        s.Fps = (int)FpsSlider.Value;
        s.BufferMinutes = (int)BufferSlider.Value;
        s.CaptureBackend = ((ComboBoxItem)CaptureBackendBox.SelectedItem).Tag?.ToString() ?? "ddagrab";
        s.CaptureMaxHeight = int.Parse(((ComboBoxItem)MaxHeightBox.SelectedItem).Tag?.ToString() ?? "720");
        s.OverlayCorner = ((ComboBoxItem)OverlayCornerBox.SelectedItem).Tag?.ToString() ?? "tr";
        _host.ApplySettings(s);
        MessageBox.Show("Ayarlar kaydedildi. Yakalama yeniden başlatıldı.", AppPaths.DisplayName);
    }

    protected override void OnClosing(System.ComponentModel.CancelEventArgs e)
    {
        e.Cancel = true;
        Hide();
    }
}
