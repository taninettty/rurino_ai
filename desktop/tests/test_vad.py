from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vad import EndOfSpeech

FRAME = 0.05


def feed(detector, level, seconds):
    """Feed one frame per 50 ms and return the detector's answers."""
    return [detector.feed(level, FRAME) for _ in range(round(seconds / FRAME))]


class EndOfSpeechTests(unittest.TestCase):
    def test_quiet_then_speech_then_pause_reports_the_end_once(self):
        detector = EndOfSpeech()
        self.assertFalse(any(feed(detector, 0.0, 0.5)))
        self.assertFalse(any(feed(detector, 0.2, 1.0)))
        pause = feed(detector, 0.0, 1.5)
        self.assertEqual(pause.count(True), 1, '只能报告一次结束')
        self.assertTrue(pause[-1] is False, '报告后必须锁存')

    def test_end_needs_the_configured_pause(self):
        detector = EndOfSpeech(silence=0.9)
        feed(detector, 0.0, 0.4)
        feed(detector, 0.2, 1.0)
        self.assertFalse(any(feed(detector, 0.0, 0.7)))
        self.assertTrue(any(feed(detector, 0.0, 0.35)))

    def test_longer_pause_setting_waits_longer(self):
        detector = EndOfSpeech(silence=1.5)
        feed(detector, 0.0, 0.4)
        feed(detector, 0.2, 1.0)
        self.assertFalse(any(feed(detector, 0.0, 1.3)))
        self.assertTrue(any(feed(detector, 0.0, 0.3)))

    def test_cough_does_not_send(self):
        detector = EndOfSpeech()
        feed(detector, 0.0, 0.5)
        feed(detector, 0.3, 0.1)
        self.assertFalse(any(feed(detector, 0.0, 3.0)))

    def test_continuous_speech_never_sends(self):
        detector = EndOfSpeech()
        self.assertFalse(any(feed(detector, 0.2, 8.0)))

    def test_noisy_room_still_detects_the_end(self):
        detector = EndOfSpeech()
        feed(detector, .02, 1.0)
        self.assertFalse(any(feed(detector, .2, 1.0)))
        self.assertTrue(any(feed(detector, .02, 2.0)))

    def test_quiet_speech_in_a_silent_room_is_heard(self):
        detector = EndOfSpeech()
        feed(detector, 0.0, 0.5)
        feed(detector, 0.06, 1.0)
        self.assertTrue(any(feed(detector, 0.0, 1.2)))

    def test_unusable_samples_are_ignored(self):
        detector = EndOfSpeech()
        feed(detector, 0.2, 0.5)
        for value in (float('nan'), float('inf'), -1.0, None, 'loud'):
            self.assertFalse(detector.feed(value, FRAME))
        self.assertFalse(detector.finished)
        self.assertTrue(any(feed(detector, 0.0, 1.2)))

    def test_reset_rearms_the_detector(self):
        detector = EndOfSpeech()
        feed(detector, 0.2, 1.0)
        self.assertTrue(any(feed(detector, 0.0, 1.2)))
        detector.reset()
        self.assertFalse(detector.finished)
        feed(detector, 0.2, 1.0)
        self.assertTrue(any(feed(detector, 0.0, 1.2)))

    def test_invalid_settings_are_rejected(self):
        for kwargs in ({'silence': 0}, {'silence': -1}, {'minimum_speech': -0.1},
                       {'noise_ratio': 1.0}, {'calibration': -1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                EndOfSpeech(**kwargs)


if __name__ == '__main__':
    unittest.main()
