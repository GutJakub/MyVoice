import subprocess
import tempfile
from pathlib import Path

from openai import OpenAI


class TTS:
    def __init__(self):
        self.client = OpenAI()

    def speak(self, text: str) -> None:
        if not text.strip():
            return

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            audio_path = Path(tmp.name)

        response = self.client.audio.speech.create(
            model="gpt-4o-mini-tts",
            voice="marin",
            input=text,
            response_format="wav",
        )

        response.write_to_file(audio_path)

        subprocess.run(
            ["paplay", str(audio_path)],
            check=True,
        )

        audio_path.unlink(missing_ok=True)