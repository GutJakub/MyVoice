import argparse
import re
from contextlib import closing

from agents import set_trace_processors
from langsmith.integrations.openai_agents_sdk import (
    OpenAIAgentsTracingProcessor,
)

from myvoice.actions.system import SystemActions
from myvoice.asr.transcriber import Transcriber
from myvoice.audio.recorder import AudioRecorder
from myvoice.audio.utterance import UtteranceRecorder
from myvoice.audio.vad import VoiceActivityDetector
from myvoice.commands.router import CommandRouter
from myvoice.wakeword.detector import WakeWordDetector
from myvoice.agent.assistant import run_command
from myvoice.integrations.windows_audio import (
    WindowsAudioController,
)


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("--debug-audio", action="store_true",
                        help="Print wake-word scores while listening")
    parser.add_argument(
        "--keyboard",
        action="store_true",
        help="Read commands from the keyboard instead of the microphone",
    )
    args = parser.parse_args()

    audio_controller = WindowsAudioController()
    system_actions = SystemActions(audio_controller=audio_controller)
    command_router = CommandRouter(
        system_actions=system_actions,
    )
    setup_tracing()
    
    if args.keyboard:
        run_keyboard_mode(command_router)
        return

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

                print(f"MyVoice: {execute_command(command, command_router)}")

                print("\nSłucham...")

    except KeyboardInterrupt:
        print("\nZatrzymano.")
    except RuntimeError as error:
        print(f"Audio stopped: {error}")


def execute_command(command: str, command_router: CommandRouter) -> str:
    response = command_router.route(command)
    if response is None:
        response = run_command(command)

    return response


def run_keyboard_mode(command_router: CommandRouter) -> None:
    print("Tryb klawiatury. Wpisz komendę lub 'exit', aby zakończyć.")

    try:
        while True:
            text = input("Ty: ").strip()

            if text.lower() in {"exit", "quit"}:
                break

            command = extract_command(text)
            if not command:
                continue

            print(f"MyVoice: {execute_command(command, command_router)}")
    except (EOFError, KeyboardInterrupt):
        pass

    print("Zatrzymano.")

def setup_tracing() -> None:
    set_trace_processors(
        [
            OpenAIAgentsTracingProcessor()
        ]
    )

def extract_command(text: str) -> str:
    command = re.sub(r"^\s*(?:(?:hey|hi)[\s,!.:-]*)?jarvis\b[\s,!.?:-]*", "", text, flags=re.IGNORECASE)
    return command.strip()


if __name__ == "__main__":
    main()
