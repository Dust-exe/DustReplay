using System.IO;
using System.Windows.Media.Imaging;

namespace DustReplay.App.Branding;

public static class BrandingPaths
{
    public static string LogoPath
    {
        get
        {
            var bundled = Path.Combine(AppContext.BaseDirectory, "Assets", "logo.png");
            if (File.Exists(bundled)) return bundled;
            var desktop = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.Desktop),
                "dasasd", "dust logo.png");
            if (File.Exists(desktop)) return desktop;
            return bundled;
        }
    }

    public static BitmapImage? LoadLogo(int decodeWidth = 0)
    {
        var path = LogoPath;
        if (!File.Exists(path)) return null;
        try
        {
            var img = new BitmapImage();
            img.BeginInit();
            img.CacheOption = BitmapCacheOption.OnLoad;
            img.UriSource = new Uri(path, UriKind.Absolute);
            if (decodeWidth > 0) img.DecodePixelWidth = decodeWidth;
            img.EndInit();
            img.Freeze();
            return img;
        }
        catch
        {
            return null;
        }
    }
}
