from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import persona
from say import pick_template, render


class PersonaRuleTests(unittest.TestCase):
    def test_self_reference_passes(self):
        self.assertTrue(persona.check('ルリも一緒に行くよ。')[0])

    def test_tic_passes(self):
        self.assertTrue(persona.check('まあなんとかなるっしょ。')[0])

    def test_exclamation_passes(self):
        self.assertTrue(persona.check('おっしゃー！')[0])

    def test_assistant_tone_rejected(self):
        ok, reason = persona.check('作为一个AI，我建议您先休息。')
        self.assertFalse(ok)
        self.assertIn('助手腔', reason)

    def test_polite_japanese_rejected(self):
        ok, reason = persona.check('その件については後ほどご連絡いたします。')
        self.assertFalse(ok)
        self.assertIn('助手腔', reason)

    def test_too_many_sentences_rejected(self):
        ok, reason = persona.check('ルリだよ。今日は暑いね。少し休もっか。もう一回言うよ。')
        self.assertFalse(ok)
        self.assertIn('句子过多', reason)

    def test_missing_marker_rejected(self):
        ok, reason = persona.check('今日はいい天気ですね。')
        self.assertFalse(ok)
        self.assertIn('缺少自称', reason)

    def test_empty_rejected(self):
        self.assertFalse(persona.check('   ')[0])

    def test_ensure_falls_back(self):
        self.assertEqual(persona.ensure('作为一个AI，我建议您。', 'ルリだよっす。'), 'ルリだよっす。')

    def test_ensure_keeps_good_line(self):
        line = 'おっしゃー！ルリも行くよ。'
        self.assertEqual(persona.ensure(line, 'fallback'), line)

    def test_style_prompt_mentions_tics(self):
        prompt = persona.style_prompt()
        self.assertIn('ルリ', prompt)
        self.assertIn('っしょ', prompt)


class TemplateConformanceTests(unittest.TestCase):
    def test_every_hour_of_day_stays_in_character(self):
        for hour in range(24):
            with self.subTest(hour=hour):
                line = render(pick_template(hour), hour)['ja']
                ok, reason = persona.check(line)
                self.assertTrue(ok, f'{hour}点模板不贴合：{reason} → {line}')

    def test_templates_keep_the_hour_fact(self):
        for hour in (8, 13, 21):
            with self.subTest(hour=hour):
                line = render(pick_template(hour), hour)['ja']
                self.assertIn(f'{hour}時', line)


if __name__ == '__main__':
    unittest.main()
