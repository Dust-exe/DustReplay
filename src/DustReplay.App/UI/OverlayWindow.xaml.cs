using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;
using DustReplay.Core;

namespace DustReplay.App.UI;

public partial class OverlayWindow : Window
{
    private const int GwlExstyle = -20;
    private const int WsExLayered = 0x80000;
    private const int WsExTransparent = 0x20;
    private const int WsExToolwindow = 0x80;
    private AppSettings _settings;

    public OverlayWindow(AppSettings settings)
    {
        InitializeComponent();
        _settings = settings;
    }

    public void ApplySettings(AppSettings s)
    {
        _settings = s;
        if (s.OverlayEnabled) ShowDot();
        else Hide();
    }

    public void ShowDot()
    {
        PositionCorner();
        Show();
        var hwnd = new WindowInteropHelper(this).Handle;
        var ex = GetWindowLongPtr(hwnd, GwlExstyle).ToInt64();
        SetWindowLongPtr(hwnd, GwlExstyle, (IntPtr)(ex | WsExLayered | WsExTransparent | WsExToolwindow));
    }

    private void PositionCorner()
    {
        var vs = SystemParameters.WorkArea;
        const int margin = 12;
        var corner = (_settings.OverlayCorner ?? "tr").ToLowerInvariant();
        Left = corner switch
        {
            "tl" => vs.Left + margin,
            "bl" => vs.Left + margin,
            "br" => vs.Right - Width - margin,
            _ => vs.Right - Width - margin,
        };
        Top = corner is "bl" or "br" ? vs.Bottom - Height - margin : vs.Top + margin;
    }

    [DllImport("user32.dll", EntryPoint = "GetWindowLongPtr")]
    private static extern IntPtr GetWindowLongPtr(IntPtr hWnd, int nIndex);

    [DllImport("user32.dll", EntryPoint = "SetWindowLongPtr")]
    private static extern IntPtr SetWindowLongPtr(IntPtr hWnd, int nIndex, IntPtr dwNewLong);
}
