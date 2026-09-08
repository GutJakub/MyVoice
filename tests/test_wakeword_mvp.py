from collections.abc import Generator
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import numpy as np

from myvoice.audio.utterance import UtteranceRecorder
from myvoice.asr.transcriber import Transcriber
from myvoice.main import extract_command


class Source:
    def __init__(self, count):
        self.chunks = [np.full(512, i / 1000, dtype=np.float32) for i in range(count)]

    def stream(self) -> Generator[np.ndarray, None, None]:
        yield from self.chunks


class WakeWordMvpTests(unittest.TestCase):
    def recorder(self, events, detections):
        source = Source(len(events))
        vad = Mock()
        vad.process.side_effect = events
        wake = Mock()
        wake.process.side_effect = detections
        return UtteranceRecorder(source, vad, wake_detector=wake), source

    def test_speech_without_wake_is_never_yielded(self):
        recorder, _ = self.recorder(
            [{'start': 0}, None, {'end': 1}] * 2, [False] * 6)
        self.assertEqual(list(recorder.listen()), [])

    def test_wake_keeps_phrase_and_command_then_rearms(self):
        recorder, source = self.recorder(
            [None, {'start': 1}, None, {'end': 3}, {'start': 4}, None, {'end': 6}],
            [False, True, False, False, False])
        utterances = list(recorder.listen())
        self.assertEqual(len(utterances), 1)
        np.testing.assert_array_equal(utterances[0], np.concatenate(source.chunks[:4]))

    def test_wake_only_allows_one_followup_command(self):
        recorder, _ = self.recorder(
            [{'start': 0}, {'end': 1}, {'start': 2}, None, {'end': 4},
             {'start': 5}, {'end': 6}], [True, False, False])
        stream = recorder.listen()
        next(stream)  # Wake phrase alone, acknowledged by main.
        recorder.awaiting_command = True
        next(stream)  # Command without a second wake phrase.
        self.assertEqual(list(stream), [])  # Later speech requires another wake.

    def test_followup_window_expires_without_authorizing_later_speech(self):
        recorder, _ = self.recorder(
            [None] * 313 + [{'start': 313}, {'end': 314}], [False, False])
        recorder.awaiting_command = True
        self.assertEqual(list(recorder.listen()), [])

    def test_transcription_accepts_audio_in_memory(self):
        transcriber = Transcriber.__new__(Transcriber)
        transcriber.model = Mock()
        transcriber.model.transcribe.return_value = (
            iter([SimpleNamespace(text='Hey Jarvis, what time is it?')]), None)
        audio = np.zeros(16000, dtype=np.float32)
        text = transcriber.transcribe(audio)
        self.assertIs(transcriber.model.transcribe.call_args.args[0], audio)
        self.assertEqual(extract_command(text), 'what time is it?')
        self.assertEqual(extract_command('Hey Jarvis.'), '')


if __name__ == '__main__':
    unittest.main()
