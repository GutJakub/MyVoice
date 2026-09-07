"""Record Windows RAW audio or replay an existing pair through AEC3."""
import argparse
import json
from pathlib import Path
import time

import numpy as np
from scipy.io import wavfile

from myvoice.audio.echo_canceller import SAMPLE_RATE, process_echo
from myvoice.audio.windows_aec_capture import capture_pair, read_capture


def read_wav(path: Path) -> np.ndarray:
    rate, audio = wavfile.read(path)
    if rate != SAMPLE_RATE or audio.ndim != 1:
        raise ValueError(f"{path}: expected 16 kHz mono WAV")
    if audio.dtype == np.int16:
        return audio.astype(np.float32) / 32768
    if audio.dtype in (np.float32, np.float64) and np.isfinite(audio).all():
        return audio.astype(np.float32)
    raise ValueError(f"{path}: expected PCM16 or finite floating-point WAV")


def window_diagnostics(mic: np.ndarray, cleaned: np.ndarray) -> list[dict]:
    """Report level changes without treating near-end speech as residual echo."""
    windows = []
    for start in range(0, mic.size, 2 * SAMPLE_RATE):
        end = min(start + 2 * SAMPLE_RATE, mic.size)
        before = float(np.mean(mic[start:end].astype(np.float64) ** 2))
        after = float(np.mean(cleaned[start:end].astype(np.float64) ** 2))
        windows.append({
            "start_seconds": start / SAMPLE_RATE,
            "end_seconds": end / SAMPLE_RATE,
            "mic_rms": before ** 0.5,
            "cleaned_rms": after ** 0.5,
            "level_reduction_db": float(10 * np.log10(before / after))
            if before > 0 and after > 0 else None,
        })
    return windows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--delay-ms", type=int, default=0, help="AEC3 buffer-delay hint, not a manual signal shift")
    parser.add_argument("--aec-output", choices=("linear", "suppressed"), default="suppressed",
                        help="Linear subtraction preserves speech; suppressed adds residual-echo suppression")
    parser.add_argument("--mic-wav", type=Path)
    parser.add_argument("--reference-wav", type=Path)
    parser.add_argument("--capture-file", type=Path, help="Replay timestamped Windows .mva capture")
    parser.add_argument("--output-dir", type=Path,
                        default=Path("recordings") / time.strftime("aec-%Y%m%d-%H%M%S"))
    args = parser.parse_args()
    if not 1 <= args.seconds <= 120 or not 0 <= args.delay_ms <= 500:
        parser.error("seconds must be 1–120; delay-ms must be 0–500")
    if bool(args.mic_wav) != bool(args.reference_wav):
        parser.error("Supply both WAV inputs together")
    if args.capture_file and args.mic_wav:
        parser.error("Choose WAV replay or capture-file replay")
    stats = {"backend": "myvoice-aec3 / pywebrtc-audio 0.2.0 native source", "delay_hint_ms": args.delay_ms,
             "selected_output": args.aec_output, "output_latency_compensated_samples": {"linear": 64, "suppressed": 128}}
    if args.mic_wav:
        mic, reference = read_wav(args.mic_wav), read_wav(args.reference_wav)
    else:
        if args.capture_file:
            mic, reference, capture_stats = read_capture(args.capture_file)
        else:
            print("Windows RAW capture: keep TV playing. First 11 s: stay silent; then speak over TV.", flush=True)
            mic, reference, capture_stats = capture_pair(args.seconds, args.output_dir)
        stats["capture"] = capture_stats
        print(f"WASAPI timestamp alignment: {capture_stats['startup_offset_ms']:.2f} ms startup offset.")
        for kind in ("mic", "reference"):
            print(f"  {kind} clock deviation: {capture_stats[kind]['clock_deviation_ppm']:+.1f} ppm")
    length = min(mic.size, reference.size)
    stats["tail_samples_trimmed"] = {"mic": mic.size - length, "reference": reference.size - length}
    mic, reference = mic[:length], reference[:length]
    if not length or np.max(np.abs(reference)) < 1e-5:
        raise RuntimeError("No usable playback reference")
    start = time.monotonic()
    result = process_echo(mic, reference, args.delay_ms)
    cleaned = getattr(result, args.aec_output)
    stats["aec3_metrics"] = result.metrics
    print(f"Fixed internal reference gain: {result.metrics['reference_gain_db']:.1f} dB; saved reference is unchanged.")
    stats["processing_seconds"] = time.monotonic() - start
    stats["audio_seconds"] = length / SAMPLE_RATE
    stats["windows"] = window_diagnostics(mic, cleaned)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    # Float WAVs preserve captured levels and allow exact offline replay.
    for name, audio in (("mic_before", mic), ("reference", reference), ("mic_after_aec", cleaned),
                        ("mic_after_aec_linear", result.linear), ("mic_after_aec_suppressed", result.suppressed)):
        wavfile.write(args.output_dir / f"{name}.wav", SAMPLE_RATE, audio.astype(np.float32))
        rms = float(np.sqrt(np.mean(audio.astype(np.float64) ** 2)))
        stats[name] = {"rms": rms, "peak": float(np.max(np.abs(audio))),
                       "samples_at_or_above_full_scale": int((np.abs(audio) >= 1).sum())}
        print(f"{name}: RMS={rms:.6f}, peak={stats[name]['peak']:.4f}")
    print("Per-window level reduction (not ERLE; includes your voice and AEC startup):")
    for window in stats["windows"]:
        reduction = window["level_reduction_db"]
        label = f"{reduction:+.1f} dB" if reduction is not None else "n/a (zero energy)"
        print(f"  {window['start_seconds']:5.1f}–{window['end_seconds']:5.1f} s: {label}")
    (args.output_dir / "aec_diagnostics.json").write_text(json.dumps(stats, indent=2) + "\n")
    print(f"Saved {length / SAMPLE_RATE:.2f} s to {args.output_dir.resolve()}. AEC only; no NS or AGC.")
    print(f"Selected {args.aec_output} output. Both AEC stages are saved for equal-volume comparison.")
    print("Listen for TV reduction AND preserved near-end speech. RMS reduction alone is not an AEC score.")


if __name__ == "__main__":
    main()
