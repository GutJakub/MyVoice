import wave
import numpy as np


def get_rms(path: str) -> float:
    with wave.open(path, "rb") as wav_file:
        audio = np.frombuffer(
            wav_file.readframes(wav_file.getnframes()),
            dtype=np.int16,
        ).astype(np.float32)

    return np.sqrt(np.mean(audio ** 2))