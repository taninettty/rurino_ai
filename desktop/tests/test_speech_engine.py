from pathlib import Path
import sys
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from speech.server import SpeechEngine


class FakeEngine(SpeechEngine):
    def __init__(self):
        super().__init__('.')
        self.calls = []
        self.cache_limit = 8
        self.cache_entries = 2

    def _synthesize(self, text):
        self.calls.append(text)
        if text == 'fail':
            self.tts = object()  # A constructed model is not proof that inference works.
            raise RuntimeError('inference failed')
        return text.encode() * 4


class SpeechEngineTests(unittest.TestCase):
    def test_repeated_phrase_and_lru_eviction(self):
        engine = FakeEngine()
        for text in ['a', 'b', 'a', 'c', 'b']:
            self.assertEqual(engine.synthesize(text), text.encode() * 4)
        self.assertEqual(engine.calls, ['a', 'b', 'c', 'b'])
        self.assertLessEqual(engine.cache_bytes, 8)

    def test_large_clip_not_cached(self):
        engine = FakeEngine()
        engine.synthesize('large')
        engine.synthesize('large')
        self.assertEqual(engine.calls, ['large', 'large'])
        self.assertEqual(engine.cache_bytes, 0)

    def test_failure_not_marked_ready_and_can_recover(self):
        engine = FakeEngine()
        with self.assertRaises(RuntimeError):
            engine.synthesize('fail')
        self.assertFalse(engine.status()['tts_loaded'])
        self.assertEqual(engine.status()['tts_state'], 'error')
        self.assertNotIn('fail', engine.cache)
        engine.synthesize('a')
        self.assertTrue(engine.status()['tts_loaded'])
        self.assertEqual(engine.status()['tts_state'], 'ready')
        self.assertIsNone(engine.status()['tts_error'])

    def test_concurrent_duplicate_only_infers_once(self):
        engine = FakeEngine()
        barrier = threading.Barrier(2)
        results = []
        def run():
            barrier.wait()
            results.append(engine.synthesize('a'))
        threads = [threading.Thread(target=run) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(2)
        self.assertEqual(results, [b'aaaa', b'aaaa'])
        self.assertEqual(engine.calls, ['a'])


if __name__ == '__main__':
    unittest.main()
