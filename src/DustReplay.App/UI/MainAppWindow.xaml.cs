using System.Diagnostics;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using DustReplay.App.Branding;
using DustReplay.App.Controls;
using DustReplay.App.Services;
using DustReplay.Core;

namespace DustReplay.App.UI;

public partial class MainAppWindow : Window
{
    private readonly AppHost _host;
    private readonly Views.SettingsView _settingsPage;

    public MainAppWindow(AppHost host)
    {
        InitializeComponent();
        _host = host;
        _settingsPage = new Views.SettingsView(host);
        _settingsPage.Visibility = Visibility.Collapsed;
        var body = (Grid)((Grid)Content).Children[1];
        var rightCol = (Grid)body.Children[1];
        rightCol.Children.Add(_settingsPage);
        Hide();
    }

    public void ShowAndFocus(bool openSettings = false)
    {
        Show();
        Activate();
        if (openSettings) NavTo("settings");
        else NavTo("gallery");
        RefreshGallery();
    }

    public void RefreshState() { }

    public void RefreshGallery()
    {
        GalleryItems.Items.Clear();
        var dir = _host.Settings.EffectiveOutputDir;
        if (!Directory.Exists(dir)) return;
        foreach (var f in Directory.GetFiles(dir, "*.mp4").OrderByDescending(File.GetLastWriteTime))
            GalleryItems.Items.Add(BuildCard(f));
    }

    private Border BuildCard(string path)
    {
        var card = new Border
        {
            Width = 220,
            Margin = new Thickness(8),
            Background = new SolidColorBrush(Color.FromRgb(20, 16, 32)),
            CornerRadius = new CornerRadius(12),
            BorderBrush = new SolidColorBrush(Color.FromRgb(75, 55, 136)),
            BorderThickness = new Thickness(1),
            Child = BuildCardContent(path),
            Cursor = System.Windows.Input.Cursors.Hand,
        };
        card.MouseLeftButtonUp += (_, _) =>
            Process.Start(new ProcessStartInfo(path) { UseShellExecute = true });
        return card;
    }

    private UIElement BuildCardContent(string path)
    {
        var sp = new StackPanel { Margin = new Thickness(10) };
        var grid = new Grid { Height = 120 };
        grid.Children.Add(new Border { Background = new SolidColorBrush(Color.FromRgb(8, 6, 14)), CornerRadius = new CornerRadius(8) });
        TryLoadThumb(grid, path);
        grid.Children.Add(new PlayOverlay
        {
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center,
        });
        sp.Children.Add(grid);
        sp.Children.Add(new TextBlock
        {
            Text = Path.GetFileName(path),
            Foreground = (Brush)FindResource("TextBrush"),
            FontWeight = FontWeights.SemiBold,
            Margin = new Thickness(0, 8, 0, 0),
            TextTrimming = TextTrimming.CharacterEllipsis,
        });
        var playBtn = new Button { Content = "Oynat", Style = (Style)FindResource("GhostButton"), Margin = new Thickness(0, 8, 0, 0) };
        playBtn.Click += (_, _) => Process.Start(new ProcessStartInfo(path) { UseShellExecute = true });
        sp.Children.Add(playBtn);
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
            if (ff != null)
            {
                try
                {
                    Process.Start(new ProcessStartInfo(ff,
                        $"-y -ss 0.35 -i \"{videoPath}\" -vframes 1 -vf scale=280:-1 \"{jpg}\"")
                    {
                        CreateNoWindow = true,
                        UseShellExecute = false,
                    })?.WaitForExit(8000);
                }
                catch { /* ignore */ }
            }
        }
        if (!File.Exists(jpg)) return;
        try
        {
            var bmp = new BitmapImage();
            bmp.BeginInit();
            bmp.CacheOption = BitmapCacheOption.OnLoad;
            bmp.UriSource = new Uri(jpg);
            bmp.EndInit();
            grid.Children.Insert(0, new Image
            {
                Source = bmp,
                Stretch = Stretch.UniformToFill,
                Opacity = 0.5,
            });
        }
        catch { /* ignore */ }
    }

    private void Nav_Click(object sender, RoutedEventArgs e) =>
        NavTo((string)((Button)sender).Tag);

    private void NavTo(string tag)
    {
        PageGallery.Visibility = tag == "gallery" ? Visibility.Visible : Visibility.Collapsed;
        _settingsPage.Visibility = tag == "settings" ? Visibility.Visible : Visibility.Collapsed;
        var accent = (Brush)FindResource("AccentBrush");
        var clear = Brushes.Transparent;
        NavGallery.Background = tag == "gallery" ? accent : clear;
        NavRecordings.Background = tag == "recordings" ? accent : clear;
        NavSettings.Background = tag == "settings" ? accent : clear;
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

    protected override void OnClosing(System.ComponentModel.CancelEventArgs e)
    {
        e.Cancel = true;
        Hide();
    }
}
