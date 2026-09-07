using System.Runtime.InteropServices;
using NAudio.CoreAudioApi;
using NAudio.CoreAudioApi.Interfaces;

internal static class RawMicrophone
{
    internal static AudioClient OpenDefault()
    {
        var enumerator = (IDeviceEnumerator)new DeviceEnumerator();
        IDevice? device = null;
        try
        {
            Marshal.ThrowExceptionForHR(enumerator.GetDefaultAudioEndpoint(1, 0, out device));
            var iid = typeof(IRawAudioClient2).GUID;
            Marshal.ThrowExceptionForHR(device.Activate(ref iid, 23, IntPtr.Zero, out object native));
            var client = new AudioClient((IAudioClient)native);
            try
            {
                var properties = new AudioClientProperties
                {
                    cbSize = (uint)Marshal.SizeOf<AudioClientProperties>(),
                    bIsOffload = 0,
                    eCategory = AudioStreamCategory.Other,
                    Options = AudioClientStreamOptions.Raw,
                };
                Marshal.ThrowExceptionForHR(((IRawAudioClient2)native).SetClientProperties(ref properties));
                return client;
            }
            catch
            {
                client.Dispose();
                throw;
            }
        }
        finally
        {
            if (device != null) Marshal.ReleaseComObject(device);
            Marshal.ReleaseComObject(enumerator);
        }
    }

    [ComImport, Guid("BCDE0395-E52F-467C-8E3D-C4579291692E")]
    private class DeviceEnumerator { }

    [ComImport, Guid("A95664D2-9614-4F35-A746-DE8DB63617E6"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IDeviceEnumerator
    {
        [PreserveSig] int EnumAudioEndpoints(int flow, uint state, out IntPtr devices);
        [PreserveSig] int GetDefaultAudioEndpoint(int flow, int role, out IDevice device);
    }

    [ComImport, Guid("D666063F-1587-4E43-81F1-B948E807363F"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IDevice
    {
        [PreserveSig] int Activate(ref Guid iid, uint context, IntPtr parameters,
                                  [MarshalAs(UnmanagedType.IUnknown)] out object instance);
    }

    // COM interfaces must redeclare inherited slots. NAudio 2.2.1's IAudioClient2
    // omits these slots: its SetClientProperties dispatches to GetBufferSize
    // (observed AUDCLNT_E_NOT_INITIALIZED). Keep the complete native order here.
    [ComImport, Guid("726778CD-F60A-4EDA-82DE-E47610CD78AA"), InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    private interface IRawAudioClient2
    {
        [PreserveSig] int Initialize(int mode, uint flags, long duration, long period, IntPtr format, IntPtr session);
        [PreserveSig] int GetBufferSize(out uint frames);
        [PreserveSig] int GetStreamLatency(out long latency);
        [PreserveSig] int GetCurrentPadding(out uint frames);
        [PreserveSig] int IsFormatSupported(int mode, IntPtr format, out IntPtr closest);
        [PreserveSig] int GetMixFormat(out IntPtr format);
        [PreserveSig] int GetDevicePeriod(out long normal, out long minimum);
        [PreserveSig] int Start();
        [PreserveSig] int Stop();
        [PreserveSig] int Reset();
        [PreserveSig] int SetEventHandle(IntPtr handle);
        [PreserveSig] int GetService(ref Guid iid, [MarshalAs(UnmanagedType.IUnknown)] out object service);
        [PreserveSig] int IsOffloadCapable(AudioStreamCategory category, out int capable);
        [PreserveSig] int SetClientProperties(ref AudioClientProperties properties);
        [PreserveSig] int GetBufferSizeLimits(IntPtr format, int eventDriven, out long minimum, out long maximum);
    }
}
