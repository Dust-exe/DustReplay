using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;
using DustReplay.App.Branding;

namespace DustReplay.App.Controls;

public partial class TitleBar : UserControl
{
    private Window? _window;

    public TitleBar()
    {
        InitializeComponent();
        Loaded += (_, _) =>
        {
            _window = Window.GetWindow(this);
            LogoImg.Source = BrandingPaths.LoadLogo(44);
        };
    }

    private void TitleBar_MouseLeftButtonDown(object sender, MouseButtonEventArgs e) =>
        TryDragMove(e);

    private void DragArea_MouseLeftButtonDown(object sender, MouseButtonEventArgs e) =>
        TryDragMove(e);

    private void TryDragMove(MouseButtonEventArgs e)
    {
        if (_window == null) return;
        if (e.OriginalSource is Button) return;
        if (e.ClickCount == 2)
        {
            _window.WindowState = _window.WindowState == WindowState.Maximized
                ? WindowState.Normal : WindowState.Maximized;
            return;
        }
        try
        {
            _window.DragMove();
        }
        catch
        {
            /* ignore if click released before move */
        }
    }

    private void Minimize_Click(object sender, RoutedEventArgs e) =>
        _window!.WindowState = WindowState.Minimized;

    private void Maximize_Click(object sender, RoutedEventArgs e) =>
        _window!.WindowState = _window.WindowState == WindowState.Maximized
            ? WindowState.Normal : WindowState.Maximized;

    private void Close_Click(object sender, RoutedEventArgs e) => _window?.Hide();
}
