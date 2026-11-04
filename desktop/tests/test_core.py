"""底层测试：配置、状态机、以及"调度 → 播报"的端到端链路。

这些是骨架级测试：不碰真实模型、真实 TTS、真实网络，只验证
"决定说 → 合成 → 播放 → 字幕"这条链路在装配正确时会跑通。
"""
from datetime import datetime
from pathlib import Path
import os
import sys
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PyQt5.QtCore import QCoreApplication
from PyQt5.QtTest import QTest

import config as config_module
import scheduler as scheduler_module
import states
from announcer import Announcer
from protocol_fixture import wav_bytes

app = QCoreApplication.instance() or QCoreApplication([])


class ConfigTests(unittest.TestCase):
    def test_defaults_are_consistent(self):
        cfg = config_module.Config()
        self.assertTrue(cfg.data_dir.is_dir())
        self.assertTrue(cfg.lines_file.is_file())
        self.assertEqual(cfg.endpoints.speech, 'http://127.0.0.1:8765')

    def test_env_override(self):
        old = os.environ.get('RURINO_SPEECH')
        os.environ['RURINO_SPEECH'] = 'http://127.0.0.1:9999'
        try:
            cfg = config_module.Config.load()
            self.assertEqual(cfg.endpoints.speech, 'http://127.0.0.1:9999')
        finally:
            if old is None:
                os.environ.pop('RURINO_SPEECH', None)
            else:
                os.environ['RURINO_SPEECH'] = old

    def test_check_reports_missing(self):
        cfg = config_module.Config(data_dir=Path('Z:/nowhere'),
                                   lines_file=Path('Z:/nowhere/lines.json'))
        missing = cfg.check()
        self.assertEqual(len(missing), 2)

    def test_first_audio_budget_matches_voice_spec(self):
        self.assertLessEqual(config_module.Timings().first_audio_budget, 1.5)


class StateMachineTests(unittest.TestCase):
    def test_loading_to_idle(self):
        machine = states.StateMachine()
        self.assertTrue(machine.to(states.State.IDLE))
        self.assertTrue(machine.is_idle())

    def test_loading_cannot_speak(self):
        machine = states.StateMachine()
        self.assertFalse(machine.to(states.State.SPEAKING))
        self.assertEqual(machine.state, states.State.LOADING)

    def test_idle_speaking_round_trip(self):
        machine = states.StateMachine(states.State.IDLE)
        self.assertTrue(machine.to(states.State.SPEAKING))
        self.assertTrue(machine.to(states.State.IDLE))

    def test_error_from_any_and_recover(self):
        machine = states.StateMachine(states.State.SPEAKING)
        self.assertTrue(machine.to(states.State.ERROR))
        self.assertTrue(machine.to(states.State.LOADING))
        self.assertTrue(machine.to(states.State.IDLE))

    def test_listener_called_once_per_change(self):
        machine = states.StateMachine(states.State.IDLE)
        seen = []
        machine.on_change(lambda old, new: seen.append((old, new)))
        machine.to(states.State.SPEAKING)
        machine.to(states.State.SPEAKING)     # 同状态不重复通知
        machine.to(states.State.IDLE)
        self.assertEqual(seen, [(states.State.IDLE, states.State.SPEAKING),
                                (states.State.SPEAKING, states.State.IDLE)])


class FakeVoice:
    def __init__(self):
        self.played = []
        self.current = None
        self._until = 0.0

    def load(self, path):
        self.current = Path(path)

    def play(self):
        self.played.append(self.current)
        self._until = time.monotonic() + 0.02

    def playing(self):
        return time.monotonic() < self._until

    def stop(self):
        self.current = None


def wait_for(predicate, seconds=3.0):
    end = time.monotonic() + seconds
    while time.monotonic() < end and not predicate():
        QTest.qWait(10)
    return predicate()


class PipelineTests(unittest.TestCase):
    """调度器决定说什么 → 播报队列合成并播出 → 字幕事件带文本。"""

    def test_scheduler_output_reaches_subtitles(self):
        scheduler = scheduler_module.Scheduler()
        ctx = scheduler_module.Context(now=datetime(2026, 11, 1, 8, 30))
        utterance = scheduler.tick(ctx)
        self.assertIsNotNone(utterance, '早上首次活动应当有话可说')

        voice = FakeVoice()
        announcer = Announcer(voice, lambda text: wav_bytes())
        self.addCleanup(announcer.shutdown)
        subtitles = []
        announcer.changed.connect(
            lambda kind, payload: subtitles.append(payload) if kind == 'subtitle' else None)

        count = announcer.say(utterance.ja, utterance.zh)
        self.assertGreaterEqual(count, 1)
        self.assertTrue(wait_for(lambda: len(voice.played) >= 1))
        self.assertTrue(wait_for(lambda: len(subtitles) >= count),
                        f'字幕应有 {count} 条，实际 {len(subtitles)}')
        joined = ''.join(item['ja'] for item in subtitles)
        self.assertIn('今は8時', joined, '时间事实应当随台词一起播出')

    def test_state_machine_refuses_speech_while_loading(self):
        machine = states.StateMachine()
        ctx = scheduler_module.Context(now=datetime(2026, 11, 1, 8, 30))
        scheduler = scheduler_module.Scheduler()
        utterance = scheduler.tick(ctx)
        # 加载中不允许进入说话状态，也就不该播报
        self.assertFalse(machine.to(states.State.SPEAKING))
        self.assertIsNotNone(utterance)


if __name__ == '__main__':
    unittest.main()
