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

    private void DragArea_MouseLeftButtonDown(object sender, MouseButtonEventArgs e)
    {
        if (e.ClickCount == 2 && _window != null)
            _window.WindowState = _window.WindowState == WindowState.Maximized
                ? WindowState.Normal : WindowState.Maximized;
        else
            _window?.DragMove();
    }

    private void Minimize_Click(object sender, RoutedEventArgs e) =>
        _window!.WindowState = WindowState.Minimized;

    private void Maximize_Click(object sender, RoutedEventArgs e) =>
        _window!.WindowState = _window.WindowState == WindowState.Maximized
            ? WindowState.Normal : WindowState.Maximized;

    private void Close_Click(object sender, RoutedEventArgs e) => _window?.Hide();
}
