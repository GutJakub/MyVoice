# MyVoice

Local desktop voice assistant with live Windows RAW microphone capture and WebRTC AEC3 echo cancellation.

From the project root, start the assistant:

```bash
uv run myvoice
```

Keep TV audio playing during the three-second preparation, then wait for `Ready` and say **“Hey Jarvis, what time is it?”** The response appears in the terminal. Stop with Ctrl+C.

The live path is Windows RAW microphone + playback reference → AEC3 linear audio → Hey Jarvis wake detection + VAD → transcription → command router. Capture and AEC keep running while transcription is busy.

Offline recording and replay remain available:

```bash
# Record microphone + playback and save cleaned audio (suppressed by default).
uv run python scripts/record_aec.py --seconds 25

# Check a cleaned recording with VAD only.
uv run python scripts/check_filtered_vad.py recordings/YOUR-TRIAL/mic_after_aec.wav

# Replay cleaned audio through transcription and command routing.
uv run myvoice --audio-file recordings/YOUR-TRIAL/mic_after_aec.wav
```

`uv run myvoice --no-aec` selects the original WSL microphone. `--audio-file` replays a saved recording instead of listening live. Rebuild the Windows helper with `./scripts/build_windows_aec.sh` after changing its C# source.

If the assistant reaches `Ready` but does not detect the wake phrase, run
`uv run myvoice --debug-audio` to show microphone, playback-reference and cleaned
levels in dBFS, plus the peak wake score about once per second. A score of 0.5
triggers detection. Live AEC defaults to `linear`, without residual-echo suppression,
following improved wake detection in a user trial. This can leave more TV audio.
Use `uv run myvoice --aec-output suppressed --debug-audio` to compare with stronger
suppression. The output selection applies to live AEC;
WAV replay uses the audio already stored in the file.

Audio components live in `src/myvoice/audio/`, manual recording/diagnostic commands in `scripts/`, and automated tests in `tests/`.

See [setup, processing details and testing](docs/aec-offline.md).

Say “Hey Jarvis” followed by your command in one sentence. You can also wait for “Jarvis: Yes?” and then give the command within 10 seconds. Wake detection uses the existing local openWakeWord model on the selected AEC output.
