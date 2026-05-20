using System.Windows;
using DustReplay.App.Services;
using DustReplay.Core;

namespace DustReplay.App;

public partial class App : Application
{
    public static AppHost Host { get; private set; } = null!;

    private void Application_Startup(object sender, StartupEventArgs e)
    {
        Host = new AppHost();
        Host.Start();
    }

    protected override void OnExit(ExitEventArgs e)
    {
        Host?.Shutdown();
        base.OnExit(e);
    }
}
