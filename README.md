# MyVoice — wake-word MVP

Local voice assistant using the WSL microphone, openWakeWord (`Hey Jarvis`),
Silero VAD and Whisper `small.en`. Commands are in English.

```bash
uv sync --locked
uv run myvoice
```

The microphone is captured through `parecord` from the WSLg `RDPSource` device
at 16 kHz mono. `parecord` must be installed (Ubuntu package: `pulseaudio-utils`).
Model files must be available locally or downloaded on first use.

Wait for the listening message, then say **“Hey Jarvis, what time is it?”**
You can also say **“Hey Jarvis”**, wait for **“Jarvis: Yes?”**, and give your
command within 10 seconds. Stop with Ctrl+C.

```text
WSL microphone → Hey Jarvis → speech endpoint detection → Whisper → command
```

The wake detector gates transcription: ordinary speech without a detected wake
phrase is not sent to Whisper. After a command, the assistant waits for another
wake phrase. A false wake detection can still open the command window.

Audio is passed to Whisper in memory; the app does not save recordings.
There is no project-level AEC, playback-reference capture or TV pause/resume in
this MVP. Windows/WSLg microphone processing may still apply.

For wake-word scores:

```bash
uv run myvoice --debug-audio
```

The TV filtration prototype is preserved on the `tv_filtration` branch.
After verifying this MVP live, commit it before experimenting with TV pause/resume
on a separate branch.

Run regression tests with `uv run python -m unittest discover -s tests -v`.
