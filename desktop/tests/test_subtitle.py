from pathlib import Path
import sys
import threading
import unittest
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chat_client import TRANSLATE_PROMPT, clean_translation, translate_reply
from protocol_fixture import protocol_server


def subtitle_requests(requests):
    return [body for kind, body in requests if kind == 'chat' and body.get('stream') is False]


class SubtitleTranslationTests(unittest.TestCase):
    def test_translates_with_a_single_dedicated_request(self):
        with protocol_server() as (base, requests):
            text = translate_reply(base, 'test-local', '今日は元気だよ。', threading.Event())
        self.assertEqual(text, '今天也很有精神哦。要聊聊天吗？')
        sent = subtitle_requests(requests)
        self.assertEqual(len(sent), 1, '只允许一次翻译请求')
        body = sent[0]
        self.assertEqual(body['model'], 'test-local')
        self.assertEqual(body['messages'][0], {'role': 'system', 'content': TRANSLATE_PROMPT})
        self.assertEqual(body['messages'][1], {'role': 'user', 'content': '今日は元気だよ。'})
        self.assertFalse(body['think'])
        self.assertLessEqual(body['options']['temperature'], .3, '翻译必须比聊天更确定')

    def test_conversation_history_is_not_sent_to_the_translator(self):
        with protocol_server() as (base, requests):
            translate_reply(base, 'test-local', 'おはよう。', threading.Event())
        self.assertEqual(len(subtitle_requests(requests)[0]['messages']), 2)

    def test_server_error_is_reported(self):
        with protocol_server() as (base, _):
            with self.assertRaises(HTTPError):
                translate_reply(base, 'test-local', 'CTRL:error', threading.Event())

    def test_untranslated_japanese_is_rejected(self):
        with protocol_server() as (base, _):
            with self.assertRaisesRegex(ValueError, '日文原文'):
                translate_reply(base, 'test-local', 'CTRL:raw', threading.Event())

    def test_empty_and_non_chinese_answers_are_rejected(self):
        with protocol_server() as (base, _):
            with self.assertRaisesRegex(ValueError, '没有拿到中文译文'):
                translate_reply(base, 'test-local', 'CTRL:empty', threading.Event())
            with self.assertRaisesRegex(ValueError, '没有返回中文译文'):
                translate_reply(base, 'test-local', 'CTRL:latin', threading.Event())

    def test_cancelled_request_does_not_touch_the_service(self):
        with protocol_server() as (base, requests):
            cancelled = threading.Event()
            cancelled.set()
            self.assertEqual(translate_reply(base, 'test-local', 'おはよう。', cancelled), '')
        self.assertEqual(subtitle_requests(requests), [])

    def test_clean_translation_normalises_output(self):
        self.assertEqual(clean_translation('  「今天也很有精神哦。」  '), '今天也很有精神哦。')
        self.assertEqual(clean_translation('第一行\n第二行'), '第一行 第二行')
        self.assertEqual(len(clean_translation('好' * 400)), 300)

    def test_only_loopback_addresses_are_accepted(self):
        with self.assertRaises(ValueError):
            translate_reply('https://api.example.com', 'test-local', 'おはよう。', threading.Event())


if __name__ == '__main__':
    unittest.main()
