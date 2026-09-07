"""Offline paired Windows capture, aligned using WASAPI sample timestamps."""
from dataclasses import dataclass, field
import json
from math import gcd
from pathlib import Path
import struct
import subprocess
from typing import BinaryIO

import numpy as np
from scipy.signal import resample_poly

SAMPLE_RATE = 16000
MAGIC = b"MVAEC001"
PACKET = struct.Struct("<BBIQQ")
DEFAULT_HELPER = (Path(__file__).resolve().parents[3] / "windows" / "WindowsAecCapture"
                  / "bin" / "Release" / "net8.0-windows" / "WindowsAecCapture.exe")


def _read_exact(stream: BinaryIO, size: int) -> bytes:
    data = stream.read(size)
    if len(data) != size:
        raise ValueError("Truncated Windows audio capture")
    return data


@dataclass
class _Track:
    sample_rate: int
    channels: int
    format: str
    chunks: list[np.ndarray] = field(default_factory=list)
    positions: list[int] = field(default_factory=list)
    timestamps: list[int] = field(default_factory=list)
    next_position: int | None = None

    def append(self, flags: int, timestamp: int, position: int, payload: bytes) -> None:
        if flags & 2:
            raise ValueError("WASAPI reported an unreliable timestamp; repeat capture")
        if flags & 1 and self.chunks:
            raise ValueError("WASAPI reported a discontinuity; repeat capture")
        if self.next_position is not None and position != self.next_position:
            raise ValueError("Missing or overlapping WASAPI samples; repeat capture")
        width = {"float32": 4, "pcm16": 2, "pcm32": 4}[self.format]
        if not payload or len(payload) % (width * self.channels):
            raise ValueError("Invalid Windows audio packet size")
        dtype = {"float32": "<f4", "pcm16": "<i2", "pcm32": "<i4"}[self.format]
        audio = np.frombuffer(payload, dtype=dtype).astype(np.float32)
        if self.format != "float32":
            audio /= 2 ** (width * 8 - 1)
        if not np.isfinite(audio).all():
            raise ValueError("Non-finite samples from Windows capture")
        audio = audio.reshape(-1, self.channels).mean(axis=1)
        if self.timestamps and timestamp <= self.timestamps[-1]:
            raise ValueError("Nonmonotonic WASAPI timestamps")
        self.chunks.append(audio)
        self.positions.append(position)
        self.timestamps.append(timestamp)
        self.next_position = position + audio.size

    def timeline(self) -> tuple[np.ndarray, float, float, dict]:
        if len(self.chunks) < 3:
            raise ValueError("Too few Windows audio packets")
        # Fit native sample positions against the common host clock. This retains
        # sample continuity and estimates the small difference between device clocks.
        positions = np.asarray(self.positions, dtype=np.float64) - self.positions[0]
        timestamps = (np.asarray(self.timestamps, dtype=np.float64) - self.timestamps[0]) / 1e7
        period, intercept = np.polyfit(positions, timestamps, 1)
        ppm = (period * self.sample_rate - 1) * 1e6
        residual_ms = float(np.max(np.abs(timestamps - (positions * period + intercept))) * 1000)
        if abs(ppm) > 2000 or residual_ms > 2:
            raise ValueError(f"Unstable Windows audio clock: {ppm:.0f} ppm, {residual_ms:.2f} ms residual")
        audio = np.concatenate(self.chunks)
        divisor = gcd(self.sample_rate, SAMPLE_RATE)
        audio = resample_poly(audio, SAMPLE_RATE // divisor, self.sample_rate // divisor).astype(np.float32)
        start = self.timestamps[0] / 1e7 + intercept
        output_period = period * self.sample_rate / SAMPLE_RATE
        stats = {"native_sample_rate": self.sample_rate, "native_channels": self.channels,
                 "clock_deviation_ppm": float(ppm), "timestamp_fit_max_error_ms": residual_ms,
                 "first_sample_qpc_seconds": start, "packets": len(self.chunks)}
        return audio, start, output_period, stats


def read_capture(path: Path) -> tuple[np.ndarray, np.ndarray, dict]:
    with path.open("rb") as stream:
        if _read_exact(stream, len(MAGIC)) != MAGIC:
            raise ValueError("Invalid Windows AEC capture header")
        length, = struct.unpack("<I", _read_exact(stream, 4))
        if not 1 <= length <= 65536:
            raise ValueError("Invalid Windows AEC metadata size")
        metadata = json.loads(_read_exact(stream, length))
        if metadata.get("mic_raw") is not True:
            raise ValueError("Windows microphone was not opened in RAW mode")
        tracks = {}
        for item in metadata["streams"]:
            if (item["id"] not in (0, 1) or item["id"] in tracks
                    or item["format"] not in ("float32", "pcm16", "pcm32")
                    or not 8000 <= item["sample_rate"] <= 192000
                    or not 1 <= item["channels"] <= 8):
                raise ValueError("Unsupported Windows audio stream format")
            tracks[item["id"]] = _Track(item["sample_rate"], item["channels"], item["format"])
        if set(tracks) != {0, 1}:
            raise ValueError("Windows capture needs microphone and reference streams")
        while header := stream.read(PACKET.size):
            if len(header) != PACKET.size:
                raise ValueError("Truncated Windows audio packet header")
            kind, flags, length, timestamp, position = PACKET.unpack(header)
            if kind not in tracks or length > 8 * 192000 * 4:
                raise ValueError("Invalid Windows audio packet")
            tracks[kind].append(flags, timestamp, position, _read_exact(stream, length))
    mic, mic_start, mic_period, mic_stats = tracks[0].timeline()
    ref, ref_start, ref_period, ref_stats = tracks[1].timeline()
    start = max(mic_start, ref_start)
    end = min(mic_start + (mic.size - 1) * mic_period,
              ref_start + (ref.size - 1) * ref_period)
    count = int((end - start) * SAMPLE_RATE) + 1
    if count < SAMPLE_RATE:
        raise ValueError("Less than one second of overlapping Windows audio")
    # Use relative seconds to avoid precision loss with long-running QPC clocks.
    times = np.arange(count) / SAMPLE_RATE
    near = np.interp((start - mic_start + times) / mic_period, np.arange(mic.size), mic)
    far = np.interp((start - ref_start + times) / ref_period, np.arange(ref.size), ref)
    stats = {"backend": "windows-raw", "metadata": metadata, "mic": mic_stats,
             "reference": ref_stats, "common_start_qpc_seconds": start,
             "startup_offset_ms": (ref_start - mic_start) * 1000}
    return near.astype(np.float32), far.astype(np.float32), stats


def capture_pair(seconds: float, output_dir: Path, helper: Path = DEFAULT_HELPER) -> tuple[np.ndarray, np.ndarray, dict]:
    if not helper.is_file():
        raise RuntimeError(f"Build the Windows RAW capture helper first; missing {helper}. "
                           "See docs/aec-offline.md.")
    output_dir.mkdir(parents=True, exist_ok=True)
    capture_path = output_dir / "capture.mva"
    # Keep the original packets for offline timing/format diagnosis.
    with capture_path.open("wb") as stream:
        try:
            result = subprocess.run([str(helper), "--seconds", str(seconds)], stdout=stream,
                                    stderr=subprocess.PIPE, timeout=seconds + 15, check=False)
        except subprocess.TimeoutExpired as error:
            raise RuntimeError("Windows RAW capture timed out") from error
    if result.returncode:
        raise RuntimeError("Windows RAW capture failed: " + result.stderr.decode(errors="replace").strip())
    return read_capture(capture_path)
