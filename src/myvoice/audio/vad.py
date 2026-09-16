import numpy as np
import torch

from silero_vad import VADIterator, load_silero_vad


class VoiceActivityDetector:
    def __init__(
        self,
        sample_rate: int = 16000,
        threshold: float = 0.5,
        min_silence_duration_ms: int = 700,
    ):
        self.sample_rate = sample_rate

        # Ładujemy model Silero tylko raz
        self.model = load_silero_vad()

        # Iterator pamięta stan pomiędzy kolejnymi chunkami audio
        self.iterator = VADIterator(
            self.model,
            sampling_rate=sample_rate,
            threshold=threshold,
            min_silence_duration_ms=min_silence_duration_ms,
        )

    def process(self, audio_chunk: np.ndarray) -> dict | None:
        tensor = torch.from_numpy(audio_chunk)

        return self.iterator(
            tensor,
            return_seconds=True,
        )

    def reset(self) -> None:
        self.iterator.reset_states()