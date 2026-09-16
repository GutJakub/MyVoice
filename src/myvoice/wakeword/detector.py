import numpy as np
from openwakeword.model import Model


class WakeWordDetector:
    def __init__(
        self,
        threshold: float = 0.5,
        debug_audio: bool = False,
    ):
        self.threshold = threshold
        self.debug_audio = debug_audio
        self._debug_frames = 0
        self._debug_peak = 0.0
        self.buffer = np.empty(0, dtype=np.float32)

        self.model = Model(
            wakeword_models=["hey_jarvis"],
            inference_framework="onnx",
        )

    def reset(self) -> None:
        self.buffer = np.empty(0, dtype=np.float32)
        self.model.reset()
        self._debug_frames = 0
        self._debug_peak = 0.0

    def process(self, audio_chunk: np.ndarray) -> bool:
        self.buffer = np.concatenate((self.buffer, audio_chunk))
        detected = False
        while self.buffer.size >= 1280:
            frame, self.buffer = self.buffer[:1280], self.buffer[1280:]
            audio_int16 = (np.clip(frame, -1.0, 1.0) * 32767).astype(np.int16)
            predictions = self.model.predict(audio_int16)
            score = float(predictions.get("hey_jarvis", 0.0))
            detected |= score >= self.threshold
            if self.debug_audio:
                self._debug_peak = max(self._debug_peak, score)
                self._debug_frames += 1
                if self._debug_frames == 13:
                    print(f"Wake score: {self._debug_peak:.3f} / {self.threshold:.3f}", flush=True)
                    self._debug_frames = 0
                    self._debug_peak = 0.0
        return bool(detected)
