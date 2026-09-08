"""Continuous Windows RAW capture → aligned AEC3 → 512-sample audio chunks."""
from collections.abc import Generator
import json
from pathlib import Path
from queue import Empty, Full, Queue
import struct
import subprocess
from tempfile import TemporaryFile
import threading
import time

import numpy as np

from myvoice.audio.echo_canceller import StreamingEchoCanceller
from myvoice.audio.frame_alignment import AudioGap, FrameAligner
from myvoice.audio.windows_aec_capture import DEFAULT_HELPER, MAGIC, PACKET, _read_exact


class LiveAecSource:
    def __init__(self, helper: Path = DEFAULT_HELPER, aec_output: str = "linear",
                 debug_audio: bool = False) -> None:
        self.helper = helper
        self.aec_output = aec_output
        self.debug_audio = debug_audio
        self.discontinuity_count = 0

    def stream(self) -> Generator[np.ndarray, None, None]:
        if not self.helper.is_file():
            raise RuntimeError('Missing Windows audio helper. Run ./scripts/build_windows_aec.sh')
        # About two seconds maximum. AEC continues while Whisper is busy;
        # an overflow is reported to VAD instead of joining unrelated audio.
        output: Queue[tuple[int, np.ndarray]] = Queue(maxsize=64)
        stopped = threading.Event()
        failure: list[Exception] = []
        print('Preparing TV echo cancellation (3 seconds). Keep the TV playing...', flush=True)
        with TemporaryFile() as errors:
            process = subprocess.Popen([str(self.helper), '--stream'], stdout=subprocess.PIPE,
                                       stderr=errors, bufsize=65536)
            assert process.stdout is not None

            def run() -> None:
                sequence = 0
                pending = np.empty(0, dtype=np.float32)
                calibration: list[tuple[np.ndarray, np.ndarray]] = []
                aec: StreamingEchoCanceller | None = None
                levels = np.zeros(3, dtype=np.float64)
                level_frames = 0
                try:
                    stream = process.stdout
                    if _read_exact(stream, len(MAGIC)) != MAGIC:
                        raise RuntimeError('Windows helper returned an invalid header')
                    size, = struct.unpack('<I', _read_exact(stream, 4))
                    if not 1 <= size <= 65536:
                        raise RuntimeError('Invalid Windows capture metadata')
                    metadata = json.loads(_read_exact(stream, size))
                    aligner = FrameAligner(metadata)
                    if self.debug_audio:
                        print(f"Audio devices: {metadata['streams']}", flush=True)
                    while not stopped.is_set():
                        header = stream.read(PACKET.size)
                        if len(header) != PACKET.size:
                            raise RuntimeError('Windows audio capture stopped')
                        kind, flags, size, stamp, position = PACKET.unpack(header)
                        if not 0 < size <= 8 * 192000 * 4:
                            raise RuntimeError('Invalid Windows audio packet size')
                        data = _read_exact(stream, size)
                        try:
                            aligner.append(kind, flags, stamp, position, data)
                            while (pair := aligner.pop()) is not None:
                                mic, reference = pair
                                if aec is None:
                                    calibration.append(pair)
                                    if len(calibration) < 300:
                                        continue
                                    far = np.concatenate([x[1] for x in calibration])
                                    rms = float(np.sqrt(np.mean(far.astype(np.float64) ** 2)))
                                    peak = float(np.max(np.abs(far)))
                                    gain = max(1.0, min(32.0, .05 / max(rms, 1e-12), .95 / max(peak, 1e-12))) if peak > 1e-5 else 16.0
                                    aec = StreamingEchoCanceller(gain, output=self.aec_output)
                                    for warm_mic, warm_ref in calibration:
                                        aec.process(warm_mic, warm_ref)
                                    calibration.clear()
                                    print('Ready. Say: "Hey Jarvis, what time is it?"', flush=True)
                                    continue
                                resets = aec.resets
                                cleaned = aec.process(mic, reference)
                                if self.debug_audio:
                                    levels += [np.mean(x.astype(np.float64) ** 2)
                                               for x in (mic, reference, cleaned)]
                                    level_frames += 1
                                    if level_frames == 100:
                                        db = 10 * np.log10(np.maximum(levels / level_frames, 1e-12))
                                        print(f"Audio dBFS: mic={db[0]:.1f}, reference={db[1]:.1f}, "
                                              f"{self.aec_output}={db[2]:.1f}; AEC resets={aec.resets}", flush=True)
                                        levels.fill(0)
                                        level_frames = 0
                                if aec.resets != resets:
                                    # Prevent a partly detected command crossing an AEC reset.
                                    sequence += 1
                                    pending = np.empty(0, dtype=np.float32)
                                pending = np.concatenate((pending, cleaned))
                                while pending.size >= 512:
                                    chunk, pending = pending[:512].copy(), pending[512:]
                                    try:
                                        output.put_nowait((sequence, chunk))
                                    except Full:
                                        try:
                                            output.get_nowait()
                                        except Empty:
                                            pass
                                        output.put_nowait((sequence, chunk))
                                    sequence += 1
                        except AudioGap:
                            aligner.reset()
                            aec = None
                            calibration.clear()
                            pending = np.empty(0, dtype=np.float32)
                            sequence += 1
                            print('Audio interrupted; reconnecting the microphone and reference...', flush=True)
                except Exception as error:
                    if not stopped.is_set():
                        failure.append(error)

            worker = threading.Thread(target=run, name='myvoice-aec', daemon=True)
            worker.start()
            previous: int | None = None
            last_output = time.monotonic()
            try:
                while True:
                    if failure:
                        errors.seek(0)
                        detail = errors.read().decode(errors='replace').strip()
                        raise RuntimeError(f'{failure[0]}\n{detail}') from failure[0]
                    try:
                        sequence, chunk = output.get(timeout=.2)
                    except Empty:
                        if not worker.is_alive() and not failure:
                            raise RuntimeError('Audio processing stopped')
                        if time.monotonic() - last_output > 15:
                            raise RuntimeError('No aligned audio is arriving from Windows; restart MyVoice')
                        continue
                    last_output = time.monotonic()
                    if previous is not None and sequence != previous + 1:
                        self.discontinuity_count += 1
                    previous = sequence
                    yield chunk
            finally:
                stopped.set()
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                worker.join(timeout=3)
                process.stdout.close()
