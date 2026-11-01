from pathlib import Path
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtTest import QTest

from announcer import Announcer
from protocol_fixture import wav_bytes

application = QCoreApplication.instance() or QCoreApplication([])


class FakeVoice:
    """记录播放顺序，并用极短时长模拟播放结束，避免测试真的出声。"""

    def __init__(self, clip_seconds=0.05):
        self.clip_seconds = clip_seconds
        self.played = []
        self.current = None
        self.stop_count = 0

    def load(self, path):
        self.current = Path(path)

    def play(self):
        self.played.append(self.current)
        self._until = time.monotonic() + self.clip_seconds

    def playing(self):
        return self.current is not None and time.monotonic() < getattr(self, '_until', 0)

    def stop(self):
        self.stop_count += 1
        self.current = None


def wait_for(predicate, seconds=3.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end and not predicate():
        QTest.qWait(10)
    return predicate()


class AnnouncerTests(unittest.TestCase):
    def make(self, clip_seconds=0.0):
        voice = FakeVoice(clip_seconds)
        announcer = Announcer(voice, lambda text: wav_bytes())
        self.addCleanup(announcer.shutdown)
        return voice, announcer

    def test_splits_and_plays_every_sentence(self):
        voice, announcer = self.make()
        count = announcer.say('こんにちは。今日はいい天気だね！')
        self.assertEqual(count, 2)
        self.assertTrue(wait_for(lambda: len(voice.played) == 2),
                        f'played={len(voice.played)}')
        self.assertTrue(announcer.idle())

    def test_single_sentence_without_punctuation(self):
        voice, announcer = self.make()
        self.assertEqual(announcer.say('今日はどうだった'), 1)
        self.assertTrue(wait_for(lambda: len(voice.played) == 1))

    def test_empty_text_plays_nothing(self):
        voice, announcer = self.make()
        self.assertEqual(announcer.say('   '), 0)
        QTest.qWait(120)
        self.assertEqual(voice.played, [])

    def test_subtitle_events_carry_sentence(self):
        voice, announcer = self.make()
        seen = []
        announcer.changed.connect(lambda kind, payload: seen.append((kind, payload)))
        announcer.say('おはよう。元気？')
        self.assertTrue(wait_for(lambda: len([1 for k, _ in seen if k == 'subtitle']) == 2))
        subtitles = [p for k, p in seen if k == 'subtitle']
        self.assertEqual(subtitles[0]['ja'], 'おはよう。')
        self.assertEqual(subtitles[0]['total'], 2)

    def test_stop_lets_current_sentence_finish(self):
        voice, announcer = self.make(clip_seconds=0.4)
        announcer.say('ひとつ。ふたつ。みっつ。')
        self.assertTrue(wait_for(lambda: len(voice.played) == 1))
        announcer.stop()
        QTest.qWait(700)
        self.assertEqual(len(voice.played), 1, '停止后不应再开始新句子')

    def test_first_sentence_latency_is_recorded(self):
        voice, announcer = self.make()
        announcer.say('おはよう。')
        self.assertTrue(wait_for(lambda: announcer.last_latency is not None))
        self.assertGreaterEqual(announcer.last_latency, 0.0)
        self.assertLess(announcer.last_latency, 1.5)

    def test_synthesis_failure_reports_and_stops(self):
        voice = FakeVoice()

        def boom(text):
            raise RuntimeError('tts down')

        announcer = Announcer(voice, boom)
        self.addCleanup(announcer.shutdown)
        errors = []
        announcer.changed.connect(lambda kind, payload: errors.append(payload) if kind == 'error' else None)
        announcer.say('おはよう。')
        self.assertTrue(wait_for(lambda: errors))
        self.assertIn('合成失败', errors[0])


if __name__ == '__main__':
    unittest.main()
