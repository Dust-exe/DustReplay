using System.IO;
using System.Windows.Media.Imaging;

namespace DustReplay.App.Branding;

public static class BrandingPaths
{
    public static string LogoPath =>
        Path.Combine(AppContext.BaseDirectory, "Assets", "logo.png");

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
