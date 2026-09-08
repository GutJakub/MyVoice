import argparse
import re
from contextlib import closing
from pathlib import Path

from myvoice.actions.system import SystemActions
from myvoice.asr.transcriber import Transcriber
from myvoice.audio.recorder import AudioRecorder
from myvoice.audio.live_aec_source import LiveAecSource
from myvoice.audio.source import AudioSource
from myvoice.audio.utterance import UtteranceRecorder
from myvoice.audio.vad import VoiceActivityDetector
from myvoice.audio.wav_source import WavAudioSource
from myvoice.commands.router import CommandRouter
from myvoice.wakeword.detector import WakeWordDetector

from myvoice.integrations.windows_audio import (
    WindowsAudioController,
)
from myvoice.audio.levels import get_rms

def main():
    parser = argparse.ArgumentParser()
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument(
        "--audio-file",
        type=Path,
        help="Replay a cleaned 16 kHz mono WAV through the assistant",
    )
    inputs.add_argument("--no-aec", action="store_true", help="Use the original WSL microphone without AEC")
    parser.add_argument("--aec-output", choices=("linear", "suppressed"), default="linear",
                        help="Select live AEC output (default: linear, without residual-echo suppression)")
    parser.add_argument("--debug-audio", action="store_true",
                        help="Print audio levels and wake-word scores while listening")
    args = parser.parse_args()

    recorder: AudioSource
    if args.audio_file is not None:
        recorder = WavAudioSource(args.audio_file)
        print(f"Replaying: {args.audio_file}")
    elif args.no_aec:
        recorder = AudioRecorder()
    else:
        recorder = LiveAecSource(aec_output=args.aec_output, debug_audio=args.debug_audio)
    print("Loading speech models...", flush=True)
    vad = VoiceActivityDetector()

    utterance_recorder = UtteranceRecorder(
        recorder=recorder,
        vad=vad,
        wake_detector=WakeWordDetector(debug_audio=args.debug_audio),
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

    if not isinstance(recorder, LiveAecSource):
        print("Słucham...")

    try:
        with closing(utterance_recorder.listen()) as utterances:
            for audio in utterances:

                print("🎤 Wykryto wypowiedź")

                audio = utterance_recorder.normalize(audio)

                utterance_recorder.save_wav(
                    audio=audio,
                    output_path=output_path,
                )

                print(f"RMS (PCM16): {get_rms(str(output_path)):.1f}")
            
                print("📝 Transkrybuję...")

                text = transcriber.transcribe(
                    str(output_path)
                )

                command = extract_command(text)
                if not command:
                    utterance_recorder.awaiting_command = True
                    print("Jarvis: Yes? Say your command.")
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
    except RuntimeError as error:
        print(f"Audio stopped: {error}")

def extract_command(text: str) -> str:
    command = re.sub(r"^\s*(?:(?:hey|hi)[\s,!.:-]*)?jarvis\b[\s,!.?:-]*", "", text, flags=re.IGNORECASE)
    return command.strip()


if __name__ == "__main__":
    main()
