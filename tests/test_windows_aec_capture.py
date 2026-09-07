import json
from pathlib import Path
import struct
from tempfile import TemporaryDirectory
import unittest

import numpy as np

from myvoice.audio.windows_aec_capture import MAGIC, PACKET, read_capture


def recording(bad_flags: int = 0, missing: bool = False) -> bytes:
    streams = [{"id": 0, "sample_rate": 44100, "channels": 1, "format": "float32"},
               {"id": 1, "sample_rate": 48000, "channels": 2, "format": "float32"}]
    metadata = json.dumps({"mic_raw": True, "streams": streams}).encode()
    data = bytearray(MAGIC + struct.pack('<I', len(metadata)) + metadata)
    for packet in range(200):
        for item in streams:
            kind, rate, channels = item['id'], item['sample_rate'], item['channels']
            frames = rate // 100
            position = packet * frames
            period = (1 + (120 if kind == 0 else -80) / 1e6) / rate
            start = 10000 + kind * 0.08
            times = start + (position + np.arange(frames)) * period
            audio = np.repeat((0.1 * np.sin(2 * np.pi * 997 * times))[:, None], channels, axis=1)
            payload = audio.astype('<f4').tobytes()
            flags = 1 if packet == 0 else (bad_flags if packet == 30 else 0)
            if missing and kind == 0 and packet == 30:
                continue
            data.extend(PACKET.pack(kind, flags, len(payload), round((start + position * period) * 1e7), position + 12345))
            data.extend(payload)
    return bytes(data)


class WindowsCaptureTests(unittest.TestCase):
    def read(self, data):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'capture.mva'
            path.write_bytes(data)
            return read_capture(path)

    def test_common_clock_alignment_resampling_and_clock_drift(self):
        mic, reference, stats = self.read(recording())
        self.assertEqual(mic.dtype, np.float32)
        self.assertEqual(mic.shape, reference.shape)
        self.assertGreater(mic.size, 30000)
        self.assertAlmostEqual(stats['mic']['clock_deviation_ppm'], 120, places=1)
        self.assertAlmostEqual(stats['reference']['clock_deviation_ppm'], -80, places=1)
        self.assertGreater(np.corrcoef(mic[100:-100], reference[100:-100])[0, 1], 0.999)
        self.assertLess(np.sqrt(np.mean((mic[100:-100] - reference[100:-100]) ** 2)), 0.002)

    def test_rejects_gaps_and_bad_timestamps(self):
        for data in (recording(bad_flags=1), recording(bad_flags=2), recording(missing=True)):
            with self.subTest():
                with self.assertRaises(ValueError):
                    self.read(data)

    def test_rejects_truncated_capture(self):
        with self.assertRaisesRegex(ValueError, 'Truncated'):
            self.read(recording()[:-1])


if __name__ == '__main__':
    unittest.main()
