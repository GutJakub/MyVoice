"""WebRTC AEC3 processing for aligned 16 kHz mono audio."""
from dataclasses import dataclass

import numpy as np
from myvoice_aec3 import EchoCanceller as _NativeEchoCanceller

SAMPLE_RATE = 16000
FRAME_SIZE = 160  # AEC3 operates on 10 ms frames.


@dataclass
class AecResult:
    linear: np.ndarray
    suppressed: np.ndarray
    metrics: dict


class StreamingEchoCanceller:
    """One persistent AEC3 instance, returning the selected 10 ms output frame."""

    def __init__(self, reference_gain: float = 1.0, output: str = "suppressed") -> None:
        if output not in ("linear", "suppressed"):
            raise ValueError("AEC output must be linear or suppressed")
        self.output = output
        self.reference_gain = reference_gain
        self.resets = 0
        self.clipped_mic_samples = 0
        self._engine = _NativeEchoCanceller(delay_ms=0)

    def process(self, mic: np.ndarray, reference: np.ndarray) -> np.ndarray:
        mic = np.asarray(mic, dtype=np.float32)
        reference = np.asarray(reference, dtype=np.float32)
        for name, frame in (("microphone", mic), ("reference", reference)):
            if frame.shape != (FRAME_SIZE,):
                raise ValueError(f"Expected 160 mono samples from {name}")
            if not np.isfinite(frame).all():
                raise ValueError(f"Non-finite samples from {name}")
        # Float capture and the resampling filter can overshoot full scale.
        # Saturate only those samples at the native normalized-PCM boundary;
        # do not change the gain of every frame or reset the learned echo path.
        self.clipped_mic_samples += int(np.count_nonzero(np.abs(mic) > 1.0))
        mic = np.clip(mic, -1.0, 1.0)
        peak = float(np.max(np.abs(reference)))
        if peak * self.reference_gain > .98:
            # A changed Windows volume can exceed the calibrated headroom.
            # Reduce the fixed gain and relearn instead of clipping reference.
            self.reference_gain = .9 / peak
            self._engine = _NativeEchoCanceller(delay_ms=0)
            self.resets += 1
        linear, suppressed = self._engine.process(
            np.ascontiguousarray(mic, dtype=np.float32),
            np.ascontiguousarray(reference * self.reference_gain, dtype=np.float32),
        )
        cleaned = linear if self.output == "linear" else suppressed
        if not np.isfinite(cleaned).all():
            raise RuntimeError("AEC3 returned non-finite samples")
        return np.clip(cleaned, -1.0, 1.0)


def process_echo(mic: np.ndarray, reference: np.ndarray, delay_ms: int = 0) -> AecResult:
    """Keep one AEC3 instance, export both stages and compensate their latency."""
    if mic.ndim != 1 or reference.shape != mic.shape or not mic.size:
        raise ValueError("Expected nonempty, equally sized mono inputs")
    if not 0 <= delay_ms <= 500 or not all(np.isfinite(x).all() and np.max(np.abs(x)) <= 1 for x in (mic, reference)):
        raise ValueError("Inputs must be finite normalized audio; delay must be 0–500 ms")
    # WASAPI loopback can be very quiet despite loud acoustic playback. AEC3's
    # render activity/delay estimator has absolute level thresholds. Use one
    # bounded gain for the entire offline trial, never frame-by-frame AGC.
    peak = float(np.max(np.abs(reference)))
    rms = float(np.sqrt(np.mean(reference.astype(np.float64) ** 2)))
    reference_gain = max(1.0, min(32.0, .05 / max(rms, 1e-12), .95 / max(peak, 1e-12))) if peak > 1e-6 else 1.0
    aec = _NativeEchoCanceller(delay_ms=delay_ms)
    # This pinned WebRTC implementation delays linear output by 64 samples and
    # suppressed output by 128. Flush the tail so the last words aren't truncated.
    padded_size = ((mic.size + 128 + FRAME_SIZE - 1) // FRAME_SIZE) * FRAME_SIZE
    linear = np.empty(padded_size, dtype=np.float32)
    suppressed = np.empty(padded_size, dtype=np.float32)
    for start in range(0, padded_size, FRAME_SIZE):
        count = max(0, min(FRAME_SIZE, mic.size - start))
        near = np.zeros(FRAME_SIZE, dtype=np.float32)
        far = np.zeros(FRAME_SIZE, dtype=np.float32)
        near[:count] = mic[start:start + count]
        far[:count] = reference[start:start + count] * reference_gain
        linear[start:start + FRAME_SIZE], suppressed[start:start + FRAME_SIZE] = aec.process(near, far)
    if not np.isfinite(linear).all() or not np.isfinite(suppressed).all():
        raise RuntimeError("AEC3 returned non-finite samples")
    metrics = dict(aec.metrics)
    metrics["reference_gain_db"] = float(20 * np.log10(reference_gain))
    return AecResult(linear[64:64 + mic.size], suppressed[128:128 + mic.size], metrics)
