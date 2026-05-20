# DustReplay — C# / WPF sürümü

Python/CustomTkinter arayüzünün yerine **.NET 8 WPF** ile yazılmış masaüstü uygulaması.

## Özellikler

- **Tray** → geniş uygulama penceresi (galeri + ayarlar)
- **Alt+C** → sol ince panel (hızlı menü)
- **7/24 tampon** — kayıt sırasında ffmpeg **durdurulmaz** (kara kare / 5 sn boşluk düzeltmesi)
- Segment süresi varsayılan **30 sn**, `-reset_timestamps` kaldırıldı
- Oyun modu: Ayarlardan **gdigrab** (bazı tam ekran oyunlar için)

## Gereksinimler

- Windows 10/11 x64
- [.NET 8 SDK](https://dotnet.microsoft.com/download/dotnet/8.0)
- `ffmpeg.exe` → `dist-csharp\ffmpeg\ffmpeg.exe` veya `%APPDATA%\DustReplay\ffmpeg\ffmpeg.exe`

## Derleme

```powershell
.\build-csharp.ps1
```

Çıktı: `dist-csharp\DustReplay.exe`

## Kara kare / 5 saniyede bir siyah frame

Eski sürümde olası nedenler:

1. **F9 kaydet** → ffmpeg tamamen duruyordu → yeniden başlarken boşluk
2. **Watchdog 5 sn** → oyun yükünde ffmpeg ölünce ~5 sn’de bir restart
3. **Segment sınırı** + `reset_timestamps`

C# sürümünde:

- Export **tamponu durdurmadan** kapalı segment dosyalarını birleştirir
- Watchdog yalnızca process gerçekten öldüğünde restart eder (varsayılan 2 sn kontrol)
- Segment 30 sn, timestamps reset yok

Oyunda hâlâ sorun varsa: **Ayarlar → Yakalama → gdigrab** dene ve FPS’i 20’de tut.

## Yasal

Aynı `LICENSE` ve `LEGAL.md` geçerlidir. Kayıt yasaları ve telif kullanıcı sorumluluğundadır.
