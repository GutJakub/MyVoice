from collections import deque
from collections.abc import Generator
from pathlib import Path
import wave

import numpy as np

from myvoice.audio.source import AudioSource
from myvoice.audio.vad import VoiceActivityDetector


class UtteranceRecorder:
    def __init__(
        self,
        recorder: AudioSource,
        vad: VoiceActivityDetector,
        sample_rate: int = 16000,
    ):
        self.recorder = recorder
        self.vad = vad
        self.sample_rate = sample_rate

    def listen(self) -> Generator[np.ndarray, None, None]:
        # 16 kHz / 512 próbek ≈ 31.25 chunków na sekundę.
        # 10 chunków to około 320 ms audio.
        pre_buffer = deque(maxlen=10)

        chunks = []
        is_speaking = False

        for chunk in self.recorder.stream():
            event = self.vad.process(chunk)

            if not is_speaking:
                # cały czas pamiętamy ostatnie ~300 ms
                pre_buffer.append(chunk)

            if event and "start" in event:
                is_speaking = True

                # dokładamy audio sprzed wykrycia mowy,
                # żeby nie uciąć pierwszej sylaby
                chunks = list(pre_buffer)

            elif is_speaking:
                chunks.append(chunk)

            if event and "end" in event and is_speaking:
                is_speaking = False

                utterance = np.concatenate(chunks)

                yield utterance

                chunks = []
                pre_buffer.clear()
            

    def save_wav(
        self,
        audio: np.ndarray,
        output_path: Path,
    ) -> Path:
        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        # Wracamy z float32 [-1, 1] do standardowego PCM int16
        audio_int16 = (
            np.clip(audio, -1.0, 1.0) * 32767
        ).astype(np.int16)

        with wave.open(str(output_path), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)  # int16 = 2 bajty
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_int16.tobytes())

        return output_path

    def normalize(
        self,
        audio: np.ndarray,
        target_peak: float = 0.9,
    ) -> np.ndarray:
        
        peak = np.max(np.abs(audio))

        if peak == 0:
            return audio

        return audio * (target_peak / peak)
