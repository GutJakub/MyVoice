from collections import deque
from contextlib import closing
from collections.abc import Generator
from pathlib import Path
import wave

import numpy as np

from myvoice.audio.source import AudioSource
from myvoice.audio.vad import VoiceActivityDetector
from myvoice.wakeword.detector import WakeWordDetector


class UtteranceRecorder:
    def __init__(
        self,
        recorder: AudioSource,
        vad: VoiceActivityDetector,
        sample_rate: int = 16000,
        wake_detector: WakeWordDetector | None = None,
    ):
        self.recorder = recorder
        self.vad = vad
        self.sample_rate = sample_rate
        self.wake_detector = wake_detector
        self.awaiting_command = False

    def listen(self) -> Generator[np.ndarray, None, None]:
        pre_buffer = deque(maxlen=50 if self.wake_detector else 10)
        chunks = []
        is_speaking = False
        active = self.wake_detector is None
        elapsed = 0
        discontinuities = getattr(self.recorder, "discontinuity_count", 0)
        with closing(self.recorder.stream()) as stream:
            for chunk in stream:
                current = getattr(self.recorder, "discontinuity_count", 0)
                if current != discontinuities:
                    self.vad.reset()
                    if self.wake_detector:
                        self.wake_detector.reset()
                    chunks.clear()
                    pre_buffer.clear()
                    is_speaking = False
                    active = self.wake_detector is None
                    self.awaiting_command = False
                    elapsed = 0
                    discontinuities = current
                if self.awaiting_command:
                    self.awaiting_command = False
                    active = True
                    elapsed = 0
                event = self.vad.process(chunk)
                if not is_speaking:
                    pre_buffer.append(chunk)
                if not active:
                    if not self.wake_detector.process(chunk):
                        continue
                    print("Hey Jarvis detected — listening for your command.", flush=True)
                    active = True
                    is_speaking = True
                    chunks = list(pre_buffer)
                    elapsed = 0
                    # Include the trigger frame once, and wait for its speech end.
                    continue
                elapsed += chunk.size
                if event and "start" in event and not is_speaking:
                    is_speaking = True
                    chunks = list(pre_buffer)
                elif is_speaking:
                    chunks.append(chunk)
                ended = event and "end" in event and is_speaking
                expired = self.wake_detector is not None and elapsed >= self.sample_rate * 10
                if ended or expired:
                    utterance = np.concatenate(chunks) if ended else None
                    chunks = []
                    pre_buffer.clear()
                    is_speaking = False
                    active = self.wake_detector is None
                    elapsed = 0
                    self.vad.reset()
                    if self.wake_detector:
                        self.wake_detector.reset()
                    if utterance is not None:
                        yield utterance

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
