using System.Diagnostics;
using System.IO;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using DustReplay.Core;

namespace DustReplay.App.Controls;

public partial class GalleryStrip : UserControl
{
    public event Action? OpenFullGallery;

    public GalleryStrip() => InitializeComponent();

    public void Refresh(string outputDir, int maxItems = 8)
    {
        ThumbHost.Children.Clear();
        if (!Directory.Exists(outputDir))
        {
            EmptyText.Visibility = Visibility.Visible;
            return;
        }

        var files = Directory.GetFiles(outputDir, "*.mp4")
            .Select(f => new FileInfo(f))
            .OrderByDescending(f => f.LastWriteTimeUtc)
            .Take(maxItems)
            .ToList();

        if (files.Count == 0)
        {
            EmptyText.Visibility = Visibility.Visible;
            return;
        }
        EmptyText.Visibility = Visibility.Collapsed;

        foreach (var fi in files)
            ThumbHost.Children.Add(BuildThumbCard(fi.FullName));
    }

    private Border BuildThumbCard(string path)
    {
        var card = new Border
        {
            Width = 104,
            Height = 72,
            Margin = new Thickness(0, 0, 6, 0),
            Background = new SolidColorBrush(Color.FromRgb(20, 16, 32)),
            CornerRadius = new CornerRadius(6),
            BorderBrush = new SolidColorBrush(Color.FromRgb(75, 55, 136)),
            BorderThickness = new Thickness(1),
            Cursor = Cursors.Hand,
        };

        var grid = new Grid();
        var bg = new Border { Background = new SolidColorBrush(Color.FromRgb(14, 10, 22)) };
        grid.Children.Add(bg);
        TryLoadThumbImage(grid, path);
        grid.Children.Add(new PlayOverlay { Width = 32, Height = 32,
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Center });

        var fn = Path.GetFileName(path);
        string label;
        try
        {
            var dt = File.GetLastWriteTime(path);
            label = dt.ToString("dd.MM HH:mm");
        }
        catch { label = fn.Length > 12 ? fn[..12] : fn; }

        var lbl = new TextBlock
        {
            Text = label,
            FontSize = 8,
            Foreground = Brushes.White,
            HorizontalAlignment = HorizontalAlignment.Center,
            VerticalAlignment = VerticalAlignment.Bottom,
            Margin = new Thickness(0, 0, 0, 4),
        };
        grid.Children.Add(lbl);
        card.Child = grid;

        void Open() => Process.Start(new ProcessStartInfo(path) { UseShellExecute = true });
        card.MouseLeftButtonUp += (_, _) => Open();
        return card;
    }

    private static void TryLoadThumbImage(Grid grid, string videoPath)
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
                        $"-y -ss 0.35 -i \"{videoPath}\" -vframes 1 -vf scale=104:-1 \"{jpg}\"")
                    {
                        CreateNoWindow = true,
                        UseShellExecute = false,
                    })?.WaitForExit(6000);
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
                Opacity = 0.55,
            });
        }
        catch { /* ignore */ }
    }

    private void AllBtn_Click(object sender, RoutedEventArgs e) => OpenFullGallery?.Invoke();
}
