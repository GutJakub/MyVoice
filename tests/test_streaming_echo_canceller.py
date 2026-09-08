import unittest
from unittest.mock import patch

import numpy as np

from myvoice.audio.echo_canceller import StreamingEchoCanceller


class StreamingEchoTests(unittest.TestCase):
    def test_linear_mode_preserves_native_linear_output(self):
        with patch('myvoice.audio.echo_canceller._NativeEchoCanceller') as native:
            linear = np.full(160, .2, dtype=np.float32)
            native.return_value.process.return_value = (linear, np.zeros(160, dtype=np.float32))
            aec = StreamingEchoCanceller(output='linear')
            result = aec.process(linear, np.zeros(160, dtype=np.float32))
            np.testing.assert_array_equal(result, linear)

    def test_invalid_output_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'AEC output'):
            StreamingEchoCanceller(output='unknown')

    def test_overshoot_is_bounded_without_reset_or_frame_normalization(self):
        with patch('myvoice.audio.echo_canceller._NativeEchoCanceller') as native:
            engine = native.return_value
            engine.process.return_value = (np.zeros(160), np.full(160, 1.01, dtype=np.float32))
            aec = StreamingEchoCanceller()
            mic = np.full(160, .25, dtype=np.float32)
            mic[:2] = [1.12, -1.12]
            output = aec.process(mic, np.zeros(160, dtype=np.float32))
            near, _ = engine.process.call_args.args
            np.testing.assert_array_equal(near[:2], [1, -1])
            np.testing.assert_array_equal(near[2:], mic[2:])
            self.assertEqual(mic[0], np.float32(1.12))
            self.assertEqual(aec.clipped_mic_samples, 2)
            self.assertEqual(aec.resets, 0)
            self.assertTrue(np.all(output <= 1))

    def test_native_engine_continues_after_overrange_capture_and_loud_reference(self):
        aec = StreamingEchoCanceller(reference_gain=16)
        for amplitude in (0.1, 1.2, 0.1):
            mic = np.full(160, amplitude, dtype=np.float32)
            result = aec.process(mic, np.full(160, .2, dtype=np.float32))
            self.assertEqual(result.shape, (160,))
            self.assertTrue(np.isfinite(result).all())
            self.assertLessEqual(float(np.max(np.abs(result))), 1)

    def test_nonfinite_samples_are_rejected_with_stream_name(self):
        for index, name in ((0, 'microphone'), (1, 'reference')):
            frames = [np.zeros(160, dtype=np.float32) for _ in range(2)]
            frames[index][0] = np.nan
            with self.assertRaisesRegex(ValueError, name):
                StreamingEchoCanceller().process(*frames)


if __name__ == '__main__':
    unittest.main()
