using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using NAudio.CoreAudioApi;
using NAudio.Wave;

// One thread owns both capture clients, including GetBuffer/ReleaseBuffer.
// A packet carries the device timestamp, never the stdout delivery time.
return Run(args);

static int Run(string[] args)
{
    if (args.Length == 1 && args[0] is "--help" or "-h")
    {
        Console.Error.WriteLine("WindowsAecCapture [--seconds 1..120 | --stream]\nRAW Windows microphone and playback reference; binary MVAEC001 packets on stdout.");
        return 0;
    }

    var seconds = 20.0;
    var streamMode = args.Length == 1 && args[0] == "--stream";
    if (!streamMode && args.Length != 0 && (args.Length != 2 || args[0] != "--seconds" ||
        !double.TryParse(args[1], System.Globalization.NumberStyles.Float, System.Globalization.CultureInfo.InvariantCulture, out seconds) || !double.IsFinite(seconds) || seconds < 1 || seconds > 120))
    {
        Console.Error.WriteLine("Expected --stream or --seconds followed by a number from 1 to 120.");
        return 2;
    }

    var stop = new CancellationTokenSource();
    Console.CancelKeyPress += (_, e) => { e.Cancel = true; stop.Cancel(); };
    try
    {
        using var microphone = RawMicrophone.OpenDefault();
        using var devices = new MMDeviceEnumerator();
        using var renderDevice = devices.GetDefaultAudioEndpoint(DataFlow.Render, Role.Console);
        using var reference = renderDevice.AudioClient;
        var micFormat = microphone.MixFormat;
        var refFormat = reference.MixFormat;
        var streams = new[]
        {
            Describe(0, "mic", "Windows default microphone", micFormat),
            Describe(1, "reference", renderDevice.FriendlyName, refFormat),
        };

        // Request the native mix format without silently changing channels/rate.
        // 100 ms endpoint buffers tolerate brief transport scheduling delays.
        microphone.Initialize(AudioClientShareMode.Shared, AudioClientStreamFlags.None,
            1_000_000, 0, micFormat, Guid.Empty);
        reference.Initialize(AudioClientShareMode.Shared, AudioClientStreamFlags.Loopback,
            1_000_000, 0, refFormat, Guid.Empty);
        var micCapture = microphone.AudioCaptureClient;
        var refCapture = reference.AudioCaptureClient;

        // Keep the render engine producing timestamped loopback packets even
        // when media is paused. This stream contains only digital silence.
        using var silence = streamMode ? renderDevice.AudioClient : null;
        if (silence != null)
        {
            silence.Initialize(AudioClientShareMode.Shared, AudioClientStreamFlags.None,
                1_000_000, 0, refFormat, Guid.Empty);
            FillSilence(silence);
        }

        using var output = new BinaryWriter(Console.OpenStandardOutput(), Encoding.UTF8);
        var header = JsonSerializer.SerializeToUtf8Bytes(new { streams, mic_raw = true });
        output.Write(Encoding.ASCII.GetBytes("MVAEC001"));
        output.Write((uint)header.Length);
        output.Write(header);
        output.Flush();
        Console.Error.WriteLine($"Microphone: RAW, {micFormat}; reference: {renderDevice.FriendlyName}, {refFormat}");

        var micStarted = false;
        var refStarted = false;
        var silenceStarted = false;
        try
        {
            if (silence != null)
            {
                silence.Start();
                silenceStarted = true;
            }
            // Render first ensures that the first microphone packet has history.
            reference.Start();
            refStarted = true;
            microphone.Start();
            micStarted = true;
            var timer = Stopwatch.StartNew();
            while (!stop.IsCancellationRequested && (streamMode || timer.Elapsed.TotalSeconds < seconds))
            {
                if (silence != null) FillSilence(silence);
                Drain(refCapture, 1, refFormat.BlockAlign, output);
                Drain(micCapture, 0, micFormat.BlockAlign, output);
                output.Flush();
                Thread.Sleep(2);
            }
        }
        finally
        {
            if (micStarted) microphone.Stop();
            if (refStarted) reference.Stop();
            if (silenceStarted) silence!.Stop();
        }
        return 0;
    }
    catch (Exception error)
    {
        Console.Error.WriteLine($"Windows AEC capture failed: {error}");
        Console.Error.WriteLine("Microphone RAW mode is required; no processed-microphone fallback was used.");
        return 1;
    }
    finally
    {
        stop.Dispose();
    }
}

static void FillSilence(AudioClient client)
{
    int available = client.BufferSize - client.CurrentPadding;
    if (available <= 0) return;
    var render = client.AudioRenderClient;
    render.GetBuffer(available);
    render.ReleaseBuffer(available, AudioClientBufferFlags.Silent);
}

static object Describe(byte id, string name, string device, WaveFormat format)
{
    var encoding = format.Encoding;
    if (format is WaveFormatExtensible extensible)
    {
        if (extensible.SubFormat == new Guid("00000003-0000-0010-8000-00AA00389B71"))
            encoding = WaveFormatEncoding.IeeeFloat;
        else if (extensible.SubFormat == new Guid("00000001-0000-0010-8000-00AA00389B71"))
            encoding = WaveFormatEncoding.Pcm;
    }
    string sampleFormat = (encoding, format.BitsPerSample) switch
    {
        (WaveFormatEncoding.IeeeFloat, 32) => "float32",
        (WaveFormatEncoding.Pcm, 16) => "pcm16",
        _ => throw new NotSupportedException($"Unsupported native {name} format: {format}. Expected float32 or PCM16."),
    };
    if (format.SampleRate < 8000 || format.SampleRate > 192000 ||
        format.Channels < 1 || format.Channels > 8 ||
        format.BlockAlign != format.Channels * format.BitsPerSample / 8)
        throw new NotSupportedException($"Invalid native {name} format: {format}.");
    return new { id, name, device, sample_rate = format.SampleRate,
        channels = format.Channels, format = sampleFormat };
}

static void Drain(AudioCaptureClient capture, byte stream, int blockAlign, BinaryWriter output)
{
    while (capture.GetNextPacketSize() > 0)
    {
        var pointer = capture.GetBuffer(out int frames, out AudioClientBufferFlags flags,
            out long devicePosition, out long qpcPosition);
        if (frames == 0) return;
        byte[] bytes;
        try
        {
            bytes = new byte[checked(frames * blockAlign)];
            if ((flags & AudioClientBufferFlags.Silent) == 0)
                Marshal.Copy(pointer, bytes, 0, bytes.Length);
        }
        finally
        {
            // Release promptly, before a potentially blocking stdout write.
            capture.ReleaseBuffer(frames);
        }
        byte packetFlags = 0;
        if ((flags & AudioClientBufferFlags.DataDiscontinuity) != 0) packetFlags |= 1;
        if ((flags & AudioClientBufferFlags.TimestampError) != 0) packetFlags |= 2;
        output.Write(stream);
        output.Write(packetFlags);
        output.Write((uint)bytes.Length);
        output.Write((ulong)qpcPosition);
        output.Write((ulong)devicePosition);
        output.Write(bytes);
    }
}
