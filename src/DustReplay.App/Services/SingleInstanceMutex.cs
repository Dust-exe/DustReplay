namespace DustReplay.App.Services;

public sealed class SingleInstanceMutex : IDisposable
{
    private Mutex? _mutex;

    public bool TryAcquire()
    {
        var created = false;
        _mutex = new Mutex(true, DustReplay.Core.AppPaths.MutexName, out created);
        return created;
    }

    public void Release()
    {
        try
        {
            _mutex?.ReleaseMutex();
        }
        catch { /* ignore */ }
    }

    public void Dispose() => Release();
}
