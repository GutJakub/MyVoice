from faster_whisper import WhisperModel


class Transcriber:
    def __init__(self, model_size: str = "small.en"):
        self.model = WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
        )

    def _remove_repeated_sentences(self, text: str) -> str:
        parts = [
            part.strip()
            for part in text.split(".")
            if part.strip()
        ]

        if not parts:
            return text

        if len(set(parts)) == 1:
            return parts[0]

        return text

    def transcribe(self, audio_path: str) -> str:
        segments, _ = self.model.transcribe(
            audio_path,
            language="en",
            beam_size=5,
            condition_on_previous_text=False,
            initial_prompt=(
                'Voice assitant commands. '
                'Examples: Stop. Open Spotify. Start. '
                "Open browser. or "
                'Short English voice commands for a desktop assistant. '
            )
        )

        text = " ".join(
            segment.text.strip()
            for segment in segments
        ).strip()

        text = self._remove_repeated_sentences(text)
        
        return text