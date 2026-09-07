# Offline AEC3 test

The default test now captures the microphone **directly on Windows in RAW mode** alongside WASAPI playback. It uses WASAPI timestamps and sample positions for alignment and clock-rate correction. The assistant can replay cleaned WAVs through its existing pipeline; continuous live AEC is not connected yet.

## Connect a cleaned recording to the assistant

First extract utterances using VAD only (no transcription or actions):

```bash
uv run python scripts/check_filtered_vad.py \
  recordings/YOUR-TRIAL/mic_after_aec_suppressed.wav
```

Listen to the files saved in that trial's `vad_utterances/` directory. Then replay the same recording through transcription, the wake-phrase check and the command router:

```bash
uv run myvoice --audio-file recordings/YOUR-TRIAL/mic_after_aec_suppressed.wav
```

This second command executes recognized commands through the existing actions. Without `--audio-file`, `myvoice` still uses the original microphone recorder. WAV replay runs as fast as processing allows and ends after the file; it is not live AEC.

`AudioSource` defines the shared `stream()` interface. `WavAudioSource` supplies contiguous float32, 512-sample chunks to `UtteranceRecorder`, preserving levels and adding one second of trailing silence for the current 700 ms VAD endpoint setting. No additional echo filtering is applied to an already cleaned WAV.

## Run

From the project root:

```bash
uv sync --locked
./scripts/build_windows_aec.sh
uv run python -m unittest discover -s tests -v
uv run python scripts/record_aec.py --seconds 25
```

The Windows helper has already been built and smoke-tested on this laptop. Rebuild after changing its C# source. The script uses the installed Windows .NET 8 SDK; it also gives the generated executable the WSL execute permission.

Start TV speech before recording and keep it running. Stay silent for the first **11 seconds**, speak near the laptop over the TV for the next ten seconds, then remain silent. Check specifically whether word beginnings and quiet words remain clear. Compare all WAVs at the same volume, without independent normalization.

Each invocation creates a dated directory under `recordings/` relative to your current directory and prints its absolute path. `--output-dir PATH` chooses a directory explicitly; files in that explicit directory are overwritten.

- `capture.mva`: original native-rate Windows packets, formats, device sample positions and timestamps; live Windows capture only.
- `mic_before.wav`, `reference.wav`: aligned 16 kHz mono inputs. The saved reference is not gain-adjusted.
- `mic_after_aec.wav`: selected output; **suppressed AEC3 by default**.
- `mic_after_aec_linear.wav`: WebRTC adaptive-filter output before residual-echo suppression.
- `mic_after_aec_suppressed.wav`: WebRTC's final output including residual-echo suppression.
- `aec_diagnostics.json`: capture metadata, clock estimates, native AEC metrics, internal reference gain and two-second level changes.

Suppressed output is the default following the successful listening trial. Both stages are still saved for comparison; use `--aec-output linear` to select the linear stage instead. This does not add a separate noise suppressor or microphone AGC.

Replay original timestamped capture without recording again:

```bash
uv run python scripts/record_aec.py \
  --capture-file recordings/YOUR-TRIAL/capture.mva \
  --output-dir recordings/replay
```

Already aligned mono WAV pairs also work:

```bash
uv run python scripts/record_aec.py \
  --mic-wav windows/WindowsAudioCapture/recordings/mic_before.wav \
  --reference-wav windows/WindowsAudioCapture/recordings/reference.wav \
  --output-dir recordings/old-capture-replay
```

AEC recording uses only Windows RAW capture. The legacy WSL/reference capture branch has been removed. `recorder.py` remains because the assistant without `--audio-file` still uses it; continuous live AEC integration is a separate step.

## What was corrected

The user's original recording failed the listening test: TV speech remained during the first 11 seconds, and some near-end words were lost. Earlier two-second energy-reduction figures did not establish success. The raw microphone recording itself contained intervals near silence while the reference was active; that suggests upstream processing but does not identify which Windows/driver/WSLg component caused it.

1. **Capture and timing:** the new helper requests `AUDCLNT_STREAMOPTIONS_RAW` on the exact microphone client it initializes. It records the native format and common-host QPC timestamps for both streams. Python verifies continuity, estimates each device's clock slope, resamples and aligns the common interval. It rejects timestamp errors, sample gaps and unstable clocks instead of silently compressing missing time. RAW capture failures stop with an error.
2. **NAudio initialization:** NAudio 2.2.1's `IAudioClient2` declaration omits inherited COM method slots. Its `SetClientProperties` call produced `AUDCLNT_E_NOT_INITIALIZED` in the live check. `RawMicrophone.cs` declares the complete method order and requests RAW before initialization. This corrected helper successfully captured both native 48 kHz stereo streams on the laptop.
3. **Quiet reference:** a regression test showed that low-level reference audio can prevent the delay estimator from adapting even with a perfectly delayed synthetic echo. One fixed gain per offline recording raises the internal reference level, bounded by 32× and a 0.95 peak target. It does not normalize or amplify the saved microphone or reference, and it does not pump gain between frames. Raising reference gain alone did not solve the old WSL recording.
4. **Speech loss:** the original Python binding exports only the final suppressed output. A small local adapter exposes both native AEC3 stages without changing WebRTC's algorithms. Both stages remain available; suppressed output is now selected by default following the listening trial. Both outputs compensate their verified algorithmic latency and flush the final partial frame.

The 1.7 MB vendored archive is **source**, not a precompiled binary. Its SHA256 is verified during builds. `uv` builds the local adapter with isolated, pinned build tools; see [native adapter details](../native/myvoice-aec3/README.md). No system compiler installation or patching of site-packages is needed.

## Files and responsibilities

- `windows/WindowsAecCapture/Program.cs`: bounded capture and framed binary protocol.
- `windows/WindowsAecCapture/RawMicrophone.cs`: correct RAW-mode COM activation.
- `scripts/build_windows_aec.sh`: build with the existing Windows .NET SDK.
- `src/myvoice/audio/windows_aec_capture.py`: packet validation, resampling and timestamp alignment.
- `native/myvoice-aec3/`: narrow native wrapper, pinned source and build configuration.
- `src/myvoice/audio/echo_canceller.py`: AEC processing and `AecResult`, without recording or command-line code.
- `scripts/record_aec.py`: Windows recording, replay and comparison outputs.
- `scripts/check_filtered_vad.py`: VAD-only verification of cleaned recordings.
- `src/myvoice/audio/levels.py`: the RMS helper used by the assistant.
- `tests/test_echo_canceller.py`, `tests/test_windows_aec_capture.py`: echo/speech regressions and capture protocol/clock tests.
- `pyproject.toml`, `uv.lock`: reproducible local adapter dependency.

The legacy Python playback reader and its decoder test have been removed. The old Windows executable is not used by this AEC command. The application recorder, VAD and routing keep their existing behavior.

## Verification and limits

Automated tests include simultaneous synthetic voiced speech plus delayed echo at both normal and quiet reference levels. They compare speech with the same WebRTC high-pass filter but no echo, so phase changes from that filter are not mistaken for lost speech. Packet tests cover different native sample rates, opposing clock drift, gaps, bad timestamps and truncation. Live RAW capture and offline replay have also been exercised on this laptop.

The complete 20-second Windows capture succeeded with a roughly 5 ms startup offset, clock estimates below 1 ppm deviation, and no rejected packets. Its outputs are in `recordings/aec-raw-validation/`; these are hardware checks, not an annotated speech-intelligibility test. A separate known-speech injection into the old paired recording retained approximately 0.975 relative speech gain with 0.988 correlation through the linear stage (compared with the same high-pass filter). The original recordings remain unchanged.

These checks do not certify word intelligibility for your physical setup. The old pair cannot recover speech removed before it reached MyVoice, and its poor linear cancellation remains visible in the revised replay. The user has since confirmed that suppressed output works well in the RAW listening trial. Recheck speech preservation after changing playback volume or microphone settings; VAD inactivity is not guaranteed.

Windows RAW mode bypasses most system processing but can retain always-on endpoint/driver/hardware effects. The test currently downmixes stereo; room effects from distinct TV channels can limit a mono reference. Playback must remain active: missing loopback packets during silence are rejected rather than assigned invented timestamps. Clock fitting is an offline operation, not a finished streaming synchronizer.

Primary implementation references: [Microsoft RAW mode](https://learn.microsoft.com/en-us/windows/win32/api/audioclient/ne-audioclient-audclnt_streamoptions), [WASAPI packet timestamps](https://learn.microsoft.com/en-us/windows/win32/api/audioclient/nf-audioclient-iaudiocaptureclient-getbuffer), [NAudio 2.2.1 interface](https://github.com/naudio/NAudio/blob/v2.2.1/NAudio.Wasapi/CoreAudioApi/Interfaces/IAudioClient2.cs), [released WebRTC binding source](https://github.com/strands-labs/pywebrtc-audio/blob/v0.2.0/bindings/webrtc_audio_bindings.cpp).
