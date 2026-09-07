import subprocess
from collections.abc import Generator

import numpy as np


class AudioRecorder:
    def __init__(
        self,
        device: str = "RDPSource",
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_size: int = 512,
    ):
        self.device = device
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size

        
    def stream(self) -> Generator[np.ndarray, None, None]:
        command = [
            "parecord",
            f"--device={self.device}",
            f"--rate={self.sample_rate}",
            f"--channels={self.channels}",
            "--format=s16le",
            "--raw",
        ]

        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )

        # int16 = 2 bajty na jedną próbkę audio
        bytes_per_chunk = self.chunk_size * 2

        try:
            while True:
                raw_audio = process.stdout.read(bytes_per_chunk)

                if not raw_audio:
                    break

                audio = np.frombuffer(
                    raw_audio,
                    dtype=np.int16,
                )

                # Silero oczekuje floatów mniej więcej w zakresie -1 ... 1
                audio = audio.astype(np.float32) / 32768.0

                yield audio

        finally:
            process.terminate()
            process.wait()

    