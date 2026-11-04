from datetime import datetime, timedelta
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import scheduler
from scheduler import Context, Scheduler


def at(hour, minute=0, day=1):
    return datetime(2026, 11, day, hour, minute)


class DaySlotTests(unittest.TestCase):
    def setUp(self):
        self.s = Scheduler(rng=random.Random(0))

    def test_morning_first_activity_speaks_with_time(self):
        ctx = Context(now=at(8, 30))
        u = self.s.tick(ctx)
        self.assertIsNotNone(u)
        self.assertEqual(u.rule, 'morning')
        self.assertIn('8時', u.ja)
        self.assertIn('ルリ', u.ja)

    def test_morning_only_once_per_day(self):
        ctx = Context(now=at(8, 30))
        self.assertIsNotNone(self.s.tick(ctx))
        ctx.now = at(9, 30)
        self.assertIsNone(self.s.tick(ctx))

    def test_evening_slot(self):
        ctx = Context(now=at(19, 0))
        u = self.s.tick(ctx)
        self.assertEqual(u.rule, 'evening')
        self.assertIn('19時', u.ja)

    def test_afternoon_is_silent(self):
        self.assertIsNone(self.s.tick(Context(now=at(14, 0))))


class QuietAndGapTests(unittest.TestCase):
    def setUp(self):
        self.s = Scheduler(rng=random.Random(0))

    def test_quiet_hours_are_silent(self):
        for hour in (2, 3, 5):
            with self.subTest(hour=hour):
                self.assertIsNone(self.s.tick(Context(now=at(hour, 10))))

    def test_min_gap_blocks_second_utterance(self):
        ctx = Context(now=at(8, 0))
        self.s.tick(ctx)
        ctx.now = at(8, 10)
        self.assertIsNone(self.s.tick(ctx))

    def test_speaking_blocks(self):
        ctx = Context(now=at(8, 0), speaking=True)
        self.assertIsNone(self.s.tick(ctx))


class StateDrivenTests(unittest.TestCase):
    def setUp(self):
        self.s = Scheduler(rng=random.Random(1))

    def test_late_night_reminds_to_sleep(self):
        ctx = Context(now=at(23, 40))
        u = self.s.tick(ctx)
        self.assertEqual(u.rule, 'late_night')
        self.assertIn('寝ろ', u.ja)

    def test_late_night_once_per_day(self):
        ctx = Context(now=at(23, 40))
        self.s.tick(ctx)
        ctx.now = at(0, 30, day=2)
        self.assertIsNone(self.s.tick(ctx))

    def test_welcome_when_back_from_away(self):
        ctx = Context(now=at(15, 0), idle_seconds=3, was_away=True)
        u = self.s.tick(ctx)
        self.assertEqual(u.rule, 'welcome')

    def test_no_welcome_if_still_away(self):
        ctx = Context(now=at(15, 0), idle_seconds=300, was_away=True)
        self.assertIsNone(self.s.tick(ctx))

    def test_rest_reminder_after_long_session(self):
        ctx = Context(now=at(15, 0), active_seconds=95 * 60)
        u = self.s.tick(ctx)
        self.assertEqual(u.rule, 'rest')
        self.assertGreater(len(u.ja), 0)

    def test_no_rest_reminder_when_user_away(self):
        ctx = Context(now=at(15, 0), active_seconds=95 * 60, idle_seconds=600)
        self.assertIsNone(self.s.tick(ctx))

    def test_rest_repeats_after_interval(self):
        ctx = Context(now=at(15, 0), active_seconds=95 * 60)
        self.assertIsNotNone(self.s.tick(ctx))
        ctx.now = at(16, 20)
        ctx.active_seconds = 155 * 60
        self.assertIsNotNone(self.s.tick(ctx))


class LineSelectionTests(unittest.TestCase):
    def test_no_immediate_repeat(self):
        s = Scheduler(rng=random.Random(2))
        ctx = Context(now=at(15, 0), active_seconds=95 * 60)
        first = s.tick(ctx)
        ctx.now = at(16, 20)
        ctx.active_seconds = 155 * 60
        second = s.tick(ctx)
        self.assertNotEqual(first.ja, second.ja)

    def test_every_line_passes_persona(self):
        import persona
        for item in scheduler.LINES:
            with self.subTest(line=item['id']):
                ok, reason = persona.check(item['ja'], quoted=bool(item.get('verified')))
                self.assertTrue(ok or item.get('authored'), f"{item['id']}: {reason}")

    def test_library_has_required_scenes(self):
        for scene in ('morning', 'evening', 'late_night', 'welcome', 'rest'):
            self.assertIn(scene, scheduler.BY_SCENE, f'缺少场景 {scene}')


if __name__ == '__main__':
    unittest.main()
