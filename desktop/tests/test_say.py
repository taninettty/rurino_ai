from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from say import facts_preserved, numbers, pick_template, polish, render, split


class TemplateTests(unittest.TestCase):
    def test_pick_by_hour(self):
        self.assertEqual(pick_template(8)['id'], 'morning')
        self.assertEqual(pick_template(13)['id'], 'day')
        self.assertEqual(pick_template(21)['id'], 'evening')
        self.assertEqual(pick_template(2)['id'], 'evening')

    def test_render_fills_fact_in_both_languages(self):
        result = render(pick_template(8), 8)
        self.assertIn('8時', result['ja'])
        self.assertIn('8 点', result['zh'])

    def test_render_is_hour_aware(self):
        self.assertIn('21時', render(TEMPLATES_EVENING, 21)['ja'])


TEMPLATES_EVENING = {'id': 'evening',
                     'ja': 'こんばんは。{hour}時になったね。今日はどうだった？',
                     'zh': '晚上好，已经 {hour} 点了。'}


class FactGuardTests(unittest.TestCase):
    def test_numbers_include_fullwidth(self):
        self.assertEqual(numbers('今は８時、あと2つ'), ['2', '８'])

    def test_same_numbers_pass(self):
        self.assertTrue(facts_preserved('今は8時だよ。', '8時だね、今は。'))

    def test_changed_number_fails(self):
        self.assertFalse(facts_preserved('今は8時だよ。', '今は9時だよ。'))

    def test_dropped_number_fails(self):
        self.assertFalse(facts_preserved('今は8時だよ。', '今だよ。'))

    def test_added_number_fails(self):
        self.assertFalse(facts_preserved('今は8時だよ。', '今は8時、あと3分だよ。'))

    def test_empty_candidate_fails(self):
        self.assertFalse(facts_preserved('今は8時だよ。', '   '))


class PolishTests(unittest.TestCase):
    def test_uses_polished_when_facts_kept(self):
        out = polish('今は8時だよ。', lambda prompt, text: '8時だね、今。')
        self.assertEqual(out, '8時だね、今。')

    def test_falls_back_when_number_changes(self):
        out = polish('今は8時だよ。', lambda prompt, text: '今は9時だよ。')
        self.assertEqual(out, '今は8時だよ。')

    def test_falls_back_when_backend_raises(self):
        def boom(prompt, text):
            raise RuntimeError('ollama down')
        self.assertEqual(polish('今は8時だよ。', boom), '今は8時だよ。')

    def test_falls_back_when_too_long(self):
        out = polish('今は8時だよ。', lambda prompt, text: '今は8時だよ、' * 5)
        self.assertEqual(out, '今は8時だよ。')

    def test_cancelled_skips_backend(self):
        called = []
        out = polish('今は8時だよ。', lambda p, t: called.append(1) or 'x',
                     cancelled=type('E', (), {'is_set': lambda self: True})())
        self.assertEqual(out, '今は8時だよ。')
        self.assertEqual(called, [])


class SplitTests(unittest.TestCase):
    def test_splits_on_sentence_end(self):
        self.assertEqual(split('おはよう。今日はいい天気だね！'), ['おはよう。', '今日はいい天気だね！'])

    def test_plain_text_stays_one_part(self):
        self.assertEqual(split('今日はどうだった'), ['今日はどうだった'])

    def test_empty_returns_empty(self):
        self.assertEqual(split('   '), [])


if __name__ == '__main__':
    unittest.main()
