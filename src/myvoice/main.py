import argparse
import re
from contextlib import closing

from myvoice.actions.system import SystemActions
from myvoice.asr.transcriber import Transcriber
from myvoice.audio.recorder import AudioRecorder
from myvoice.audio.utterance import UtteranceRecorder
from myvoice.audio.vad import VoiceActivityDetector
from myvoice.commands.router import CommandRouter
from myvoice.wakeword.detector import WakeWordDetector

from myvoice.integrations.windows_audio import (
    WindowsAudioController,
)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--debug-audio", action="store_true",
                        help="Print wake-word scores while listening")
    args = parser.parse_args()

    recorder = AudioRecorder()
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

    print('Słucham. Powiedz "Hey Jarvis", a następnie komendę.', flush=True)

    try:
        with closing(utterance_recorder.listen()) as utterances:
            for audio in utterances:

                print("🎤 Wykryto wypowiedź")

                audio = utterance_recorder.normalize(audio)

                print("📝 Transkrybuję...")

                text = transcriber.transcribe(
                    audio
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

    except KeyboardInterrupt:
        print("\nZatrzymano.")
    except RuntimeError as error:
        print(f"Audio stopped: {error}")

def extract_command(text: str) -> str:
    command = re.sub(r"^\s*(?:(?:hey|hi)[\s,!.:-]*)?jarvis\b[\s,!.?:-]*", "", text, flags=re.IGNORECASE)
    return command.strip()


if __name__ == "__main__":
    main()
