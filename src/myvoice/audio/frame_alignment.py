"""Bounded, timestamp-driven alignment of two live WASAPI streams."""
from collections import deque

import numpy as np
from scipy.signal import firwin, lfilter

from myvoice.audio.echo_canceller import FRAME_SIZE, SAMPLE_RATE


class AudioGap(ValueError):
    """Capture must start a new continuous timeline."""


class _LiveTrack:
    def __init__(self, info: dict) -> None:
        self.rate = int(info['sample_rate'])
        self.channels = int(info['channels'])
        self.format = info['format']
        if not 8000 <= self.rate <= 192000 or not 1 <= self.channels <= 8:
            raise ValueError('Unsupported Windows audio format')
        if self.format not in ('float32', 'pcm16', 'pcm32'):
            raise ValueError('Unsupported Windows sample format')
        self.buffer = np.empty(0, dtype=np.float32)
        self.buffer_start = 0
        self.next_position: int | None = None
        self.first_time: float | None = None
        self.anchors: deque[tuple[int, float]] = deque(maxlen=500)
        self.period = 1 / self.rate
        self.anchor_position = 0
        self.anchor_time = 0.0
        self.cursor: float | None = None
        self.packet_count = 0
        # Causal anti-alias filtering retains state across packet boundaries.
        half = int(np.ceil(10 * self.rate / SAMPLE_RATE)) if self.rate > SAMPLE_RATE else 0
        self.taps = firwin(2 * half + 1, SAMPLE_RATE / self.rate, window=('kaiser', 5.0)) if half else np.ones(1)
        self.filter_delay = half
        self.filter_state = np.zeros(2 * half)

    def append(self, flags: int, timestamp: int, position: int, payload: bytes) -> None:
        if flags & 2 or (flags & 1 and self.next_position is not None):
            raise AudioGap('WASAPI reported a capture discontinuity')
        if self.next_position is not None and position != self.next_position:
            raise AudioGap('Missing or overlapping capture samples')
        stamp = timestamp / 1e7
        if self.anchors and stamp <= self.anchors[-1][1]:
            raise AudioGap('Nonmonotonic capture timestamps')
        dtype, scale = {'float32': ('<f4', 1), 'pcm16': ('<i2', 32768),
                        'pcm32': ('<i4', 2147483648)}[self.format]
        width = np.dtype(dtype).itemsize * self.channels
        if not payload or len(payload) % width:
            raise ValueError('Invalid audio packet size')
        audio = np.frombuffer(payload, dtype=dtype).astype(np.float32)
        if not np.isfinite(audio).all():
            raise ValueError('Invalid audio samples')
        audio = (audio.reshape(-1, self.channels) / scale).mean(axis=1)
        filtered, self.filter_state = lfilter(self.taps, [1.0], audio, zi=self.filter_state)
        if self.next_position is None:
            self.buffer_start = position
            self.first_time = stamp
            self.anchor_position, self.anchor_time = position, stamp
        self.next_position = position + audio.size
        self.buffer = np.concatenate((self.buffer, filtered.astype(np.float32)))
        self.anchors.append((position, stamp))
        self.packet_count += 1
        if self.buffer.size > self.rate * 4:
            raise AudioGap('Capture streams stopped arriving together')
        if len(self.anchors) >= 30 and self.packet_count % 10 == 0:
            positions = np.array([a[0] - position for a in self.anchors], dtype=np.float64)
            times = np.array([a[1] - stamp for a in self.anchors])
            period, offset = np.polyfit(positions, times, 1)
            if abs(period * self.rate - 1) > .002:
                raise AudioGap('Unstable audio device clock')
            self.period = float(period)
            self.anchor_position, self.anchor_time = position, stamp + float(offset)

    def sample_plan(self, when: float) -> np.ndarray | None:
        if self.first_time is None:
            return None
        target = self.anchor_position + (when - self.anchor_time) / self.period + self.filter_delay
        step = 1 / (SAMPLE_RATE * self.period)
        cursor = target if self.cursor is None else self.cursor
        # Slew towards the fitted clock rather than jumping/repeating samples.
        error = target - cursor
        if abs(error) > self.rate * .02:
            raise AudioGap('Audio clocks lost alignment')
        step += float(np.clip(error / FRAME_SIZE, -step * .0005, step * .0005))
        indices = cursor + np.arange(FRAME_SIZE + 1) * step
        if indices[0] < self.buffer_start:
            raise AudioGap('Audio buffer underrun')
        if indices[-1] > self.buffer_start + self.buffer.size - 1:
            return None
        return indices

    def consume(self, indices: np.ndarray) -> np.ndarray:
        audio = np.interp(indices[:-1] - self.buffer_start,
                          np.arange(self.buffer.size), self.buffer).astype(np.float32)
        self.cursor = float(indices[-1])
        drop = max(0, int(self.cursor) - self.buffer_start - 2)
        self.buffer = self.buffer[drop:]
        self.buffer_start += drop
        return audio


class FrameAligner:
    """Convert native packets into paired 160-sample, 16 kHz frames."""

    def __init__(self, metadata: dict) -> None:
        if metadata.get('mic_raw') is not True:
            raise ValueError('RAW microphone capture is required')
        self.info = {item['id']: item for item in metadata['streams']}
        if set(self.info) != {0, 1}:
            raise ValueError('Expected microphone and playback streams')
        self.reset()

    def reset(self) -> None:
        self.tracks = {kind: _LiveTrack(info) for kind, info in self.info.items()}
        self.start: float | None = None
        self.frames = 0

    def append(self, kind: int, flags: int, timestamp: int, position: int, payload: bytes) -> None:
        if kind not in self.tracks:
            raise ValueError('Unknown audio stream')
        self.tracks[kind].append(flags, timestamp, position, payload)

    def pop(self) -> tuple[np.ndarray, np.ndarray] | None:
        if self.start is None:
            starts = [track.first_time for track in self.tracks.values()]
            if any(value is None for value in starts):
                return None
            self.start = max(starts)
        when = self.start + self.frames * FRAME_SIZE / SAMPLE_RATE
        plans = [self.tracks[kind].sample_plan(when) for kind in (0, 1)]
        if any(plan is None for plan in plans):
            return None
        mic, reference = [self.tracks[kind].consume(plan) for kind, plan in enumerate(plans)]
        self.frames += 1
        return mic, reference
