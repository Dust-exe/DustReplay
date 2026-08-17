using System;
using System.Diagnostics;
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

    const int TARGET_SAMPLE_RATE = 48000;
    const int TARGET_CHANNELS = 2;
    const int TARGET_BYTES_PER_SAMPLE = 4; // float32
    const int TARGET_BLOCK_ALIGN = TARGET_CHANNELS * TARGET_BYTES_PER_SAMPLE; // 8 bytes per frame

    [STAThread]
    static void Main(string[] args)
    {
        try
        {
            IMMDeviceEnumerator enumerator = (IMMDeviceEnumerator)new MMDeviceEnumeratorComObject();
            IMMDevice device;
            // eRender = 0, eConsole = 0
            int hr = enumerator.GetDefaultAudioEndpoint(0, 0, out device);
            if (hr != 0 || device == null)
            {
                Console.Error.WriteLine("GetDefaultAudioEndpoint failed hr: 0x" + hr.ToString("X"));
                EmitContinuousSilence();
                return;
            }

            Guid iidAudioClient = IID_IAudioClient;
            object audioClientObj;
            hr = device.Activate(ref iidAudioClient, 23, IntPtr.Zero, out audioClientObj);
            if (hr != 0 || audioClientObj == null)
            {
                Console.Error.WriteLine("Activate failed hr: 0x" + hr.ToString("X"));
                EmitContinuousSilence();
                return;
            }
            IAudioClient audioClient = (IAudioClient)audioClientObj;

            IntPtr mixFormatPtr;
            hr = audioClient.GetMixFormat(out mixFormatPtr);
            if (hr != 0 || mixFormatPtr == IntPtr.Zero)
            {
                Console.Error.WriteLine("GetMixFormat failed hr: 0x" + hr.ToString("X"));
                EmitContinuousSilence();
                return;
            }
            WAVEFORMATEX wf = (WAVEFORMATEX)Marshal.PtrToStructure(mixFormatPtr, typeof(WAVEFORMATEX));

            int AUDCLNT_STREAMFLAGS_LOOPBACK = 0x00020000;
            long bufferDuration = 2000000; // 200ms
            Guid sessionGuid = Guid.Empty;

            hr = audioClient.Initialize(0, AUDCLNT_STREAMFLAGS_LOOPBACK, bufferDuration, 0, mixFormatPtr, ref sessionGuid);
            if (hr != 0)
            {
                Console.Error.WriteLine("Initialize failed hr: 0x" + hr.ToString("X"));
                EmitContinuousSilence();
                return;
            }

            Guid iidCaptureClient = IID_IAudioCaptureClient;
            object captureClientObj;
            hr = audioClient.GetService(ref iidCaptureClient, out captureClientObj);
            if (hr != 0 || captureClientObj == null)
            {
                Console.Error.WriteLine("GetService failed hr: 0x" + hr.ToString("X"));
                EmitContinuousSilence();
                return;
            }
            IAudioCaptureClient captureClient = (IAudioCaptureClient)captureClientObj;

            int inChannels = wf.nChannels > 0 ? (int)wf.nChannels : 2;
            int inSampleRate = wf.nSamplesPerSec > 0 ? (int)wf.nSamplesPerSec : 48000;
            int inBitsPerSample = wf.wBitsPerSample > 0 ? (int)wf.wBitsPerSample : 32;
            bool isFloat = (wf.wFormatTag == 3) || (inBitsPerSample == 32);

            using (Stream stdout = Console.OpenStandardOutput())
            {
                audioClient.Start();
                uint packetSize;
                IntPtr pData;
                uint numFrames;
                uint flags;
                ulong devPos;
                ulong qpcPos;

                Stopwatch sw = Stopwatch.StartNew();
                long totalFramesSent = 0;

                while (true)
                {
                    captureClient.GetNextPacketSize(out packetSize);
                    bool hadAudio = false;

                    while (packetSize > 0)
                    {
                        hr = captureClient.GetBuffer(out pData, out numFrames, out flags, out devPos, out qpcPos);
                        if (hr == 0 && numFrames > 0)
                        {
                            bool silent = (flags & 1) != 0 || pData == IntPtr.Zero;
                            byte[] converted = ConvertToStandardStereoFloat48k(pData, (int)numFrames, inChannels, inSampleRate, inBitsPerSample, isFloat, silent);
                            if (converted != null && converted.Length > 0)
                            {
                                stdout.Write(converted, 0, converted.Length);
                                totalFramesSent += (converted.Length / TARGET_BLOCK_ALIGN);
                                hadAudio = true;
                            }
                            captureClient.ReleaseBuffer(numFrames);
                        }
                        else
                        {
                            break;
                        }
                        captureClient.GetNextPacketSize(out packetSize);
                    }

                    // Keep clock sync: if device produces no audio packet, output silence frames to match real elapsed time
                    double elapsedSec = sw.Elapsed.TotalSeconds;
                    long expectedFrames = (long)(elapsedSec * TARGET_SAMPLE_RATE);
                    long missingFrames = expectedFrames - totalFramesSent;

                    if (missingFrames > 240) // more than 5ms behind
                    {
                        int sendSilenceFrames = (int)Math.Min(missingFrames, 4800); // max 100ms per loop
                        byte[] silence = new byte[sendSilenceFrames * TARGET_BLOCK_ALIGN];
                        stdout.Write(silence, 0, silence.Length);
                        totalFramesSent += sendSilenceFrames;
                    }

                    if (!hadAudio)
                    {
                        Thread.Sleep(5);
                    }
                }
            }
        }
        catch (Exception ex)
        {
            Console.Error.WriteLine("WASAPI Loopback fatal: " + ex.Message);
            EmitContinuousSilence();
        }
    }

    static byte[] ConvertToStandardStereoFloat48k(IntPtr pData, int numFrames, int inChannels, int inSampleRate, int inBitsPerSample, bool isFloat, bool silent)
    {
        if (numFrames <= 0) return null;

        // Extract input samples to float array [-1.0f .. 1.0f]
        float[] inSamples = new float[numFrames * inChannels];
        if (!silent && pData != IntPtr.Zero)
        {
            int bytesPerSample = inBitsPerSample / 8;
            int totalBytes = numFrames * inChannels * bytesPerSample;
            byte[] rawBytes = new byte[totalBytes];
            Marshal.Copy(pData, rawBytes, 0, totalBytes);

            int idx = 0;
            for (int i = 0; i < numFrames * inChannels; i++)
            {
                if (isFloat && bytesPerSample == 4)
                {
                    inSamples[i] = BitConverter.ToSingle(rawBytes, idx);
                }
                else if (bytesPerSample == 2) // 16-bit PCM
                {
                    short s = BitConverter.ToInt16(rawBytes, idx);
                    inSamples[i] = s / 32768.0f;
                }
                else if (bytesPerSample == 3) // 24-bit PCM
                {
                    int s = (rawBytes[idx + 0]) | (rawBytes[idx + 1] << 8) | ((sbyte)rawBytes[idx + 2] << 16);
                    inSamples[i] = s / 8388608.0f;
                }
                else if (bytesPerSample == 4) // 32-bit int PCM
                {
                    int s = BitConverter.ToInt32(rawBytes, idx);
                    inSamples[i] = s / 2147483648.0f;
                }
                idx += bytesPerSample;
            }
        }

        // Downmix / upmix channels to stereo (2 channels: left, right)
        float[] stereoSamples = new float[numFrames * 2];
        for (int i = 0; i < numFrames; i++)
        {
            if (inChannels == 1)
            {
                float m = inSamples[i];
                stereoSamples[i * 2] = m;
                stereoSamples[i * 2 + 1] = m;
            }
            else if (inChannels == 2)
            {
                stereoSamples[i * 2] = inSamples[i * 2];
                stereoSamples[i * 2 + 1] = inSamples[i * 2 + 1];
            }
            else
            {
                // Multi-channel (5.1 / 7.1): mix front-left and front-right + center
                float left = inSamples[i * inChannels + 0];
                float right = inSamples[i * inChannels + 1];
                if (inChannels >= 3)
                {
                    float center = inSamples[i * inChannels + 2] * 0.707f;
                    left += center;
                    right += center;
                }
                stereoSamples[i * 2] = Math.Max(-1.0f, Math.Min(1.0f, left));
                stereoSamples[i * 2 + 1] = Math.Max(-1.0f, Math.Min(1.0f, right));
            }
        }

        // Sample rate conversion if not 48kHz (simple linear resample)
        float[] outSamples;
        int outFrames;
        if (inSampleRate == TARGET_SAMPLE_RATE)
        {
            outSamples = stereoSamples;
            outFrames = numFrames;
        }
        else
        {
            double ratio = (double)TARGET_SAMPLE_RATE / inSampleRate;
            outFrames = (int)(numFrames * ratio);
            outSamples = new float[outFrames * 2];
            for (int i = 0; i < outFrames; i++)
            {
                double srcIdx = i / ratio;
                int srcFloor = (int)srcIdx;
                int srcNext = Math.Min(srcFloor + 1, numFrames - 1);
                double frac = srcIdx - srcFloor;

                outSamples[i * 2] = (float)((1.0 - frac) * stereoSamples[srcFloor * 2] + frac * stereoSamples[srcNext * 2]);
                outSamples[i * 2 + 1] = (float)((1.0 - frac) * stereoSamples[srcFloor * 2 + 1] + frac * stereoSamples[srcNext * 2 + 1]);
            }
        }

        // Convert float array to bytes
        byte[] result = new byte[outFrames * TARGET_BLOCK_ALIGN];
        Buffer.BlockCopy(outSamples, 0, result, 0, result.Length);
        return result;
    }

    static void EmitContinuousSilence()
    {
        try
        {
            using (Stream stdout = Console.OpenStandardOutput())
            {
                byte[] chunk = new byte[480 * TARGET_BLOCK_ALIGN]; // 10ms of silence
                while (true)
                {
                    stdout.Write(chunk, 0, chunk.Length);
                    Thread.Sleep(10);
                }
            }
        }
        catch { }
    }
}
