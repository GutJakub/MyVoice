"""Replay cleaned audio through VAD without transcription or command execution."""
import argparse
from pathlib import Path

from myvoice.audio.utterance import UtteranceRecorder
from myvoice.audio.vad import VoiceActivityDetector
from myvoice.audio.wav_source import WavAudioSource


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("audio_file", type=Path)
    args = parser.parse_args()

    source = WavAudioSource(args.audio_file)
    recorder = UtteranceRecorder(
        recorder=source,
        vad=VoiceActivityDetector(),
    )

    output_dir = args.audio_file.parent / "vad_utterances"
    count = 0
    for count, audio in enumerate(recorder.listen(), start=1):
        output_path = output_dir / f"utterance_{count:03d}.wav"
        recorder.save_wav(audio=audio, output_path=output_path)
        print(
            f"Utterance {count}: "
            f"{audio.size / 16000:.2f} seconds → {output_path}"
        )

    print(f"Finished. Detected {count} utterances.")


if __name__ == "__main__":
    main()
