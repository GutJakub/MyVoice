import unittest

import numpy as np
from scipy.signal import lfilter

from myvoice.audio.echo_canceller import process_echo


class OfflineAecTests(unittest.TestCase):
    def test_delayed_echo_attenuation_and_near_end_preservation(self):
        rng = np.random.default_rng(7)
        n = 16000 * 12 + 73
        reference = lfilter([0.3], [1, -0.7], rng.normal(0, 0.2, n)).astype(np.float32)
        mic = np.zeros(n, dtype=np.float32)
        delay = 1520
        mic[delay:] = 0.6 * reference[:-delay]
        cleaned = process_echo(mic, reference).suppressed
        tail = slice(16000 * 6, None)
        reduction = 10 * np.log10(np.mean(mic[tail] ** 2) / max(np.mean(cleaned[tail] ** 2), 1e-20))
        print(f"Synthetic delayed echo reduction: {reduction:.1f} dB")
        self.assertGreater(reduction, 10)
        self.assertEqual(cleaned.shape, mic.shape)
        near = lfilter([0.4], [1, -0.6], rng.normal(0, 0.15, n)).astype(np.float32)
        preserved = process_echo(near, np.zeros(n, dtype=np.float32)).suppressed
        ratio = np.sqrt(np.mean(preserved[tail] ** 2) / np.mean(near[tail] ** 2))
        self.assertGreater(ratio, 0.7)
        self.assertLess(ratio, 1.2)

    def test_rejects_invalid_input(self):
        with self.assertRaises(ValueError):
            process_echo(np.zeros(160), np.zeros(159))
        with self.assertRaises(ValueError):
            process_echo(np.full(160, np.nan), np.zeros(160))

    def test_final_sample_survives_frame_padding_and_output_latency(self):
        mic = np.zeros(1027, dtype=np.float32)
        mic[-1] = .5
        result = process_echo(mic, np.zeros_like(mic))
        self.assertEqual(result.linear.shape, mic.shape)
        self.assertEqual(result.suppressed.shape, mic.shape)
        self.assertGreater(abs(result.linear[-1]), .3)
        self.assertGreater(abs(result.suppressed[-1]), .3)

    def test_linear_output_preserves_double_talk_at_two_reference_levels(self):
        n = 16000 * 16 + 73
        t = np.arange(n) / 16000
        speech = sum(np.sin(2 * np.pi * f * t) / k
                     for k, f in enumerate(range(170, 3400, 170), 1))
        speech *= (.2 + .8 * np.sin(2 * np.pi * 2.5 * t) ** 2)
        speech *= (np.sin(2 * np.pi * 1.3 * t) > -.5) * .06
        speech[:16000 * 7] = 0
        speech = speech.astype(np.float32)
        # Compare with the same high-pass filtering and latency, without echo.
        expected = process_echo(speech, np.zeros(n, dtype=np.float32)).linear
        for level, echo_gain in ((.1, .6), (.0024, 2.0)):
            with self.subTest(reference_rms=level):
                rng = np.random.default_rng(505)
                far = lfilter([.3], [1, -.7], rng.normal(0, 1, n)).astype(np.float32)
                far *= level / np.std(far)
                mic = speech.copy()
                mic[1520:] += echo_gain * far[:-1520]
                result = process_echo(mic, far)
                x, y = expected[16000 * 8:], result.linear[16000 * 8:]
                self.assertGreater(np.dot(x, y) / np.dot(x, x), .9)
                self.assertGreater(np.corrcoef(x, y)[0, 1], .94)
                self.assertEqual(result.linear.size, n)
                # Echo-only portion after convergence, before speech starts.
                interval = slice(16000 * 4, 16000 * 6)
                reduction = 10 * np.log10(np.mean(mic[interval] ** 2) /
                                         np.mean(result.linear[interval] ** 2))
                self.assertGreater(reduction, 15)


if __name__ == '__main__':
    unittest.main()
