using System.Diagnostics;
using System.Text.RegularExpressions;
using DustReplay.Core;

namespace DustReplay.App.Services;

public sealed class AudioDeviceService
{
    public async Task<(List<string> micLabels, List<string> micValues,
        List<string> sysLabels, List<string> sysValues)> ListDevicesAsync()
    {
        return await Task.Run(() =>
        {
            var ff = AppPaths.ResolveFfmpeg();
            if (ff == null)
                return (new List<string> { "(Mikrofon yok)" }, new List<string> { "" },
                    new List<string> { "Windows varsayılan" }, new List<string> { "__wasapi_out__" });

            var mics = ListDshowAudio(ff);
            var micLabels = new List<string> { "(Mikrofon yok)" };
            var micValues = new List<string> { "" };
            foreach (var d in mics)
            {
                micLabels.Add(d);
                micValues.Add(d);
            }

            var sysLabels = new List<string> { "Windows varsayılan (WASAPI)", "Stereo Mix / sanal (dshow)" };
            var sysValues = new List<string> { "__wasapi_out__", "" };
            return (micLabels, micValues, sysLabels, sysValues);
        });
    }

    private static List<string> ListDshowAudio(string ffmpeg)
    {
        var list = new List<string>();
        try
        {
            var psi = new ProcessStartInfo(ffmpeg, "-hide_banner -list_devices true -f dshow -i dummy")
            {
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true,
            };
            using var p = Process.Start(psi);
            if (p == null) return list;
            var err = p.StandardError.ReadToEnd();
            p.WaitForExit(8000);
            foreach (Match m in Regex.Matches(err, @"\""([^\""]+)\"" \(audio\)"))
                if (!list.Contains(m.Groups[1].Value))
                    list.Add(m.Groups[1].Value);
        }
        catch { /* ignore */ }
        return list;
    }
}
