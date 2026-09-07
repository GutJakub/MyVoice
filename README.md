# MyVoice

Local desktop voice assistant with an offline Windows RAW/WebRTC AEC3 audio workflow.

From the project root:

```bash
# Record microphone + playback and save cleaned audio (suppressed by default).
uv run python scripts/record_aec.py --seconds 25

# Check a cleaned recording with VAD only.
uv run python scripts/check_filtered_vad.py recordings/YOUR-TRIAL/mic_after_aec.wav

# Replay cleaned audio through transcription and command routing.
uv run myvoice --audio-file recordings/YOUR-TRIAL/mic_after_aec.wav
```

`uv run myvoice` still uses the original microphone input. Continuous live AEC is not connected yet.

Audio components live in `src/myvoice/audio/`, manual recording/diagnostic commands in `scripts/`, and automated tests in `tests/`.

See [setup, processing details and testing](docs/aec-offline.md).
