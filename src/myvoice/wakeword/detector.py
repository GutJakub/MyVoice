import numpy as np
from openwakeword.model import Model


class WakeWordDetector:
    def __init__(
        self,
        threshold: float = 0.5,
    ):
        self.threshold = threshold

        self.model = Model(
            wakeword_models=["hey_jarvis"],
            inference_framework="onnx",
        )

    def process(self, audio_chunk: np.ndarray) -> bool:
        audio_int16 = (
            audio_chunk * 32767
        ).astype(np.int16)

        predictions = self.model.predict(audio_int16)

        score = predictions.get("hey_jarvis", 0.0)

        if score >= self.threshold:
            print(f"🔥 Hey Jarvis detected: {score:.2f}")
            return True

        return False