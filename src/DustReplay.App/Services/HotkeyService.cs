using System.Runtime.InteropServices;
using System.Windows.Interop;
using DustReplay.Core;

namespace DustReplay.App.Services;

/// <summary>Global hotkeys via Win32 RegisterHotKey.</summary>
public sealed class HotkeyService : IDisposable
{
    private const int WmHotkey = 0x0312;
    private HwndSource? _source;
    private readonly Dictionary<int, Action> _actions = new();
    private int _id;
    private AppSettings _settings;

    [DllImport("user32.dll")]
    private static extern bool RegisterHotKey(IntPtr hWnd, int id, uint fsModifiers, uint vk);

    [DllImport("user32.dll")]
    private static extern bool UnregisterHotKey(IntPtr hWnd, int id);

    public HotkeyService(AppSettings settings)
    {
        _settings = settings;
        var helper = new HwndSource(new HwndSourceParameters("DustReplayHotkeys")
        {
            Width = 0, Height = 0, WindowStyle = 0,
        });
        _source = helper;
        helper.AddHook(WndProc);
    }

    private Action? _save;
    private Action? _toggle;
    private Action? _panel;

    public void Rebind(AppSettings s)
    {
        UnregisterAll();
        _settings = s;
        if (_save != null) RegisterSave(_save);
        if (_toggle != null) RegisterToggle(_toggle);
        if (_panel != null) RegisterPanel(_panel);
    }

    public void RegisterSave(Action a) { _save = a; Register(_settings.HotkeySave, a); }
    public void RegisterToggle(Action a) { _toggle = a; Register(_settings.HotkeyToggle, a); }
    public void RegisterPanel(Action a) { _panel = a; Register(_settings.PanelHotkey, a); }

    private void Register(string combo, Action action)
    {
        if (_source == null) return;
        if (!TryParse(combo, out var mod, out var key)) return;
        _id++;
        var id = _id;
        _actions[id] = action;
        RegisterHotKey(_source.Handle, id, mod, key);
    }

    private IntPtr WndProc(IntPtr hwnd, int msg, IntPtr wParam, IntPtr lParam, ref bool handled)
    {
        if (msg == WmHotkey && _actions.TryGetValue((int)wParam, out var act))
        {
            act();
            handled = true;
        }
        return IntPtr.Zero;
    }

    private void UnregisterAll()
    {
        if (_source == null) return;
        for (var i = 1; i <= _id; i++)
            UnregisterHotKey(_source.Handle, i);
        _actions.Clear();
        _id = 0;
    }

    private static bool TryParse(string combo, out uint mod, out uint vk)
    {
        mod = 0;
        vk = 0;
        var parts = combo.ToLowerInvariant().Split('+').Select(p => p.Trim()).ToArray();
        if (parts.Length == 0) return false;
        var key = parts[^1];
        for (var i = 0; i < parts.Length - 1; i++)
        {
            mod |= parts[i] switch
            {
                "alt" => 0x0001,
                "ctrl" or "control" => 0x0002,
                "shift" => 0x0004,
                "win" => 0x0008,
                _ => 0u,
            };
        }
        vk = key switch
        {
            "f1" => 0x70, "f2" => 0x71, "f3" => 0x72, "f4" => 0x73,
            "f5" => 0x74, "f6" => 0x75, "f7" => 0x76, "f8" => 0x77,
            "f9" => 0x78, "f10" => 0x79, "f11" => 0x7A, "f12" => 0x7B,
            "c" => 0x43,
            _ => 0,
        };
        return vk != 0;
    }

    public void Dispose()
    {
        UnregisterAll();
        _source?.Dispose();
    }
}
