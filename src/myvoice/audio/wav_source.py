from collections.abc import Generator
from pathlib import Path

import numpy as np
from scipy.io import wavfile


class WavAudioSource:
    def __init__(
        self,
        path: Path,
        chunk_size: int = 512,
    ) -> None:
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        self.path = path
        self.chunk_size = chunk_size

    def stream(self) -> Generator[np.ndarray, None, None]:
        sample_rate, audio = wavfile.read(self.path)

        if sample_rate != 16000:
            raise ValueError("Expected a 16 kHz recording")

        if audio.ndim != 1:
            raise ValueError("Expected a mono recording")

        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0
        elif audio.dtype in (np.float32, np.float64):
            audio = audio.astype(np.float32)
        else:
            raise ValueError("Expected PCM16 or floating-point audio")

        if audio.size == 0:
            raise ValueError("The recording is empty")

        if not np.isfinite(audio).all():
            raise ValueError("The recording contains invalid samples")

        # Your VAD needs 700 ms of silence to finish an utterance.
        # Add one second so speech near the file's end can finish.
        audio = np.concatenate(
            [
                audio,
                np.zeros(16000, dtype=np.float32),
            ]
        )

        for start in range(0, audio.size, self.chunk_size):
            chunk = audio[start:start + self.chunk_size]

            # Silero must receive a complete 512-sample chunk.
            if chunk.size < self.chunk_size:
                chunk = np.pad(
                    chunk,
                    (0, self.chunk_size - chunk.size),
                )

            yield np.ascontiguousarray(chunk, dtype=np.float32)
