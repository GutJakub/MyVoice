"""Offline WebRTC AEC3 processing for aligned 16 kHz mono audio."""
from dataclasses import dataclass

import numpy as np
from myvoice_aec3 import EchoCanceller

SAMPLE_RATE = 16000
FRAME_SIZE = 160  # AEC3 operates on 10 ms frames.


@dataclass
class AecResult:
    linear: np.ndarray
    suppressed: np.ndarray
    metrics: dict


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
    aec = EchoCanceller(delay_ms=delay_ms)
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
