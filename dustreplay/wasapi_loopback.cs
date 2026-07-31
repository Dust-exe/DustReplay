using System;
using System.IO;
using System.Runtime.InteropServices;
using System.Threading;

class WasapiLoopback
{
    static readonly Guid CLSID_MMDeviceEnumerator = new Guid("BCDE0395-E52F-467C-8E3D-C4579291692E");
    static readonly Guid IID_IAudioClient = new Guid("1CB9AD4C-DBFA-4c32-B178-C2F568A703B2");
    static readonly Guid IID_IAudioCaptureClient = new Guid("C8ADBD64-E71E-48a0-A4DE-185C395CD317");

    [ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
    class MMDeviceEnumeratorComObject { }

    [Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IMMDeviceEnumerator
    {
        int EnumAudioEndpoints(int dataFlow, int dwStateMask, out IntPtr ppDevices);
        int GetDefaultAudioEndpoint(int dataFlow, int role, out IMMDevice ppEndpoint);
    }

    [Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IMMDevice
    {
        int Activate(ref Guid iid, int dwClsCtx, IntPtr pActivationParams, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface);
    }

    [Guid("1CB9AD4C-DBFA-4c32-B178-C2F568A703B2"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IAudioClient
    {
        int Initialize(int shareMode, int streamFlags, long hnsBufferDuration, long hnsPeriodicity, IntPtr pFormat, ref Guid AudioSessionGuid);
        int GetBufferSize(out uint pNumBufferFrames);
        int GetStreamLatency(out long phnsLatency);
        int GetCurrentPadding(out uint pNumPaddingFrames);
        int IsFormatSupported(int shareMode, IntPtr pFormat, out IntPtr ppClosestMatch);
        int GetMixFormat(out IntPtr ppDeviceFormat);
        int GetService(ref Guid iid, [MarshalAs(UnmanagedType.IUnknown)] out object ppInterface);
        int Start();
        int Stop();
        int Reset();
        int SetEventHandle(IntPtr eventHandle);
    }

    [Guid("C8ADBD64-E71E-48a0-A4DE-185C395CD317"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    interface IAudioCaptureClient
    {
        int GetBuffer(out IntPtr pData, out uint pNumFramesToRead, out uint pdwFlags, out ulong pu64DevicePosition, out ulong pu64QPCPosition);
        int ReleaseBuffer(uint NumFramesRead);
        int GetNextPacketSize(out uint pNumFramesInNextPacket);
    }

    [StructLayout(LayoutKind.Sequential, Pack = 1)]
    struct WAVEFORMATEX
    {
        public ushort wFormatTag;
        public ushort nChannels;
        public uint nSamplesPerSec;
        public uint nAvgBytesPerSec;
        public ushort nBlockAlign;
        public ushort wBitsPerSample;
        public ushort cbSize;
    }

    [STAThread]
    static void Main(string[] args)
    {
        try
        {
            IMMDeviceEnumerator enumerator = (IMMDeviceEnumerator)new MMDeviceEnumeratorComObject();
            IMMDevice device;
            int hr = enumerator.GetDefaultAudioEndpoint(0, 0, out device);
            if (hr != 0 || device == null)
            {
                Console.Error.WriteLine("GetDefaultAudioEndpoint hr: 0x" + hr.ToString("X"));
                return;
            }

            Guid iidAudioClient = IID_IAudioClient;
            object audioClientObj;
            hr = device.Activate(ref iidAudioClient, 23, IntPtr.Zero, out audioClientObj);
            if (hr != 0 || audioClientObj == null)
            {
                Console.Error.WriteLine("Activate hr: 0x" + hr.ToString("X"));
                return;
            }
            IAudioClient audioClient = (IAudioClient)audioClientObj;

            IntPtr mixFormatPtr;
            hr = audioClient.GetMixFormat(out mixFormatPtr);
            if (hr != 0 || mixFormatPtr == IntPtr.Zero)
            {
                Console.Error.WriteLine("GetMixFormat hr: 0x" + hr.ToString("X"));
                return;
            }
            WAVEFORMATEX wf = (WAVEFORMATEX)Marshal.PtrToStructure(mixFormatPtr, typeof(WAVEFORMATEX));

            int AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000;
            long bufferDuration = 2000000; // 200ms
            Guid sessionGuid = Guid.Empty;

            hr = audioClient.Initialize(0, AUDCLNT_STREAMFLAGS_LOOPBACK, bufferDuration, 0, mixFormatPtr, ref sessionGuid);
            if (hr != 0)
            {
                Console.Error.WriteLine("Initialize hr: 0x" + hr.ToString("X"));
                return;
            }

            Guid iidCaptureClient = IID_IAudioCaptureClient;
            object captureClientObj;
            hr = audioClient.GetService(ref iidCaptureClient, out captureClientObj);
            if (hr != 0 || captureClientObj == null)
            {
                Console.Error.WriteLine("GetService hr: 0x" + hr.ToString("X"));
                return;
            }
            IAudioCaptureClient captureClient = (IAudioCaptureClient)captureClientObj;

            using (Stream stdout = Console.OpenStandardOutput())
            {
                audioClient.Start();
                uint packetSize;
                IntPtr pData;
                uint numFrames;
                uint flags;
                ulong devPos;
                ulong qpcPos;

                while (true)
                {
                    Thread.Sleep(5);
                    captureClient.GetNextPacketSize(out packetSize);
                    while (packetSize > 0)
                    {
                        captureClient.GetBuffer(out pData, out numFrames, out flags, out devPos, out qpcPos);
                        int bytesToRead = (int)(numFrames * wf.nBlockAlign);
                        if (bytesToRead > 0)
                        {
                            byte[] buffer = new byte[bytesToRead];
                            if ((flags & 1) == 0 && pData != IntPtr.Zero)
                            {
                                Marshal.Copy(pData, buffer, 0, bytesToRead);
                            }
                            stdout.Write(buffer, 0, bytesToRead);
                            stdout.Flush();
                        }
                        captureClient.ReleaseBuffer(numFrames);
                        captureClient.GetNextPacketSize(out packetSize);
                    }
                }
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine("WASAPI Loopback Error: " + ex.Message);
        }
    }
}
