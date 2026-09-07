import argparse
from pathlib import Path

from myvoice.actions.system import SystemActions
from myvoice.asr.transcriber import Transcriber
from myvoice.audio.recorder import AudioRecorder
from myvoice.audio.source import AudioSource
from myvoice.audio.utterance import UtteranceRecorder
from myvoice.audio.vad import VoiceActivityDetector
from myvoice.audio.wav_source import WavAudioSource
from myvoice.commands.router import CommandRouter

from myvoice.integrations.windows_audio import (
    WindowsAudioController,
)
from myvoice.audio.levels import get_rms
WAKE_WORDS = (
    "my voice",
    "myvoice",
)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--audio-file",
        type=Path,
        help="Replay a cleaned 16 kHz mono WAV through the assistant",
    )
    args = parser.parse_args()

    recorder: AudioSource
    if args.audio_file is not None:
        recorder = WavAudioSource(args.audio_file)
        print(f"Replaying: {args.audio_file}")
    else:
        recorder = AudioRecorder()
    vad = VoiceActivityDetector()

    utterance_recorder = UtteranceRecorder(
        recorder=recorder,
        vad=vad,
    )

    transcriber = Transcriber(
        model_size="small.en",
    )
    
    audio_controller = WindowsAudioController()
    system_actions = SystemActions(audio_controller=audio_controller)

    command_router = CommandRouter(
        system_actions=system_actions,
    )

    output_path = Path("recordings/utterance.wav")

    print("Słucham...")

    try:
        for audio in utterance_recorder.listen():

            print("🎤 Wykryto wypowiedź")

            audio = utterance_recorder.normalize(audio)

            utterance_recorder.save_wav(
                audio=audio,
                output_path=output_path,
            )

            print(f"RMS: {get_rms(str(output_path))}")
            
            print("📝 Transkrybuję...")

            text = transcriber.transcribe(
                str(output_path)
            )

            command = extract_command(text)
            if command is None:
                print("Ignored - no wake word.")
                print("\nSłucham...")
                continue

            if not command:
                print("MyVoice: Yes?")
                print("\nSłucham...")
                continue

            print(f"Ty: {text}")

            response = command_router.route(command)
            print(f"MyVoice: {response}")

    
            print("\nSłucham...")

        if args.audio_file is not None:
            print("Replay finished.")

    except KeyboardInterrupt:
        print("\nZatrzymano.")

def extract_command(text: str) -> str | None:
    normalized = text.lower().strip()

    for wake_word in WAKE_WORDS:
        if normalized.startswith(wake_word):
            return text[len(wake_word):].strip(" ,.!?")

    return None


if __name__ == "__main__":
    main()
