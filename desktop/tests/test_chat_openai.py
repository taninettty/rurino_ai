"""DeepSeek / OpenAI 兼容后端测试：用本地假 SSE 服务验证流式解析。

不联网、不用真密钥：起一个 http.server，按 OpenAI 格式吐 SSE 分块。
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import sys
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import chat_openai
import config as config_module


class FakeSSEHandler(BaseHTTPRequestHandler):
    chunks = ['こん', 'にちは', '、ルリだよ']

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get('Content-Length', 0))
        self.rfile.read(length)
        self.send_response(200)
        self.send_header('Content-Type', 'text/event-stream')
        self.end_headers()
        for piece in self.chunks:
            body = {'choices': [{'delta': {'content': piece}}]}
            self.wfile.write(f'data: {json.dumps(body, ensure_ascii=False)}\n\n'.encode())
            self.wfile.flush()
        self.wfile.write(b'data: [DONE]\n\n')
        self.wfile.flush()

    def log_message(self, *args):
        pass


class StreamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(('127.0.0.1', 0), FakeSSEHandler)
        cls.port = cls.server.server_address[1]
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def backend(self):
        return config_module.ChatBackend(provider='deepseek',
                                   base=f'http://127.0.0.1:{self.port}',
                                   model='deepseek-chat',
                                   path='/v1/chat/completions',
                                   key_env='')

    def test_stream_collects_all_deltas(self):
        seen = []
        text = chat_openai.stream_chat(self.backend(), [{'role': 'user', 'content': 'hi'}],
                                       on_delta=seen.append)
        self.assertEqual(text, 'こんにちは、ルリだよ')
        self.assertEqual(seen, ['こん', 'にちは', '、ルリだよ'])

    def test_sends_model_and_stream_flag(self):
        captured = {}

        class Capture(FakeSSEHandler):
            def do_POST(self):  # noqa: N802
                length = int(self.headers.get('Content-Length', 0))
                captured['body'] = json.loads(self.rfile.read(length))
                captured['auth'] = self.headers.get('Authorization')
                self.send_response(200)
                self.send_header('Content-Type', 'text/event-stream')
                self.end_headers()
                self.wfile.write(b'data: [DONE]\n\n')

        server = HTTPServer(('127.0.0.1', 0), Capture)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            backend = config_module.ChatBackend(provider='deepseek', base=f'http://127.0.0.1:{server.server_address[1]}',
                                          model='deepseek-chat', path='/v1/chat/completions')
            chat_openai.stream_chat(backend, [{'role': 'user', 'content': 'x'}])
        finally:
            server.shutdown()
        self.assertEqual(captured['body']['model'], 'deepseek-chat')
        self.assertTrue(captured['body']['stream'])
        self.assertIsNone(captured['auth'])

    def test_missing_key_raises_before_request(self):
        backend = config_module.ChatBackend(provider='deepseek', base='http://127.0.0.1:1',
                                      path='/v1/chat/completions', key_env='RURINO_NO_SUCH_KEY')
        with self.assertRaises(chat_openai.MissingKey):
            chat_openai.stream_chat(backend, [{'role': 'user', 'content': 'x'}])

    def test_key_header_used_when_present(self):
        os.environ['RURINO_TEST_KEY'] = 'sk-test-123'
        try:
            backend = config_module.ChatBackend(provider='deepseek', base='http://127.0.0.1:1',
                                          path='/v1/chat/completions', key_env='RURINO_TEST_KEY')
            self.assertEqual(backend.api_key(), 'sk-test-123')
        finally:
            os.environ.pop('RURINO_TEST_KEY', None)


class ConfigBackendTests(unittest.TestCase):
    def test_default_is_ollama(self):
        backend = config_module.ChatBackend.load()
        self.assertEqual(backend.provider, 'ollama')
        self.assertIn('11434', backend.base)

    def test_deepseek_provider_from_env(self):
        old = {k: os.environ.get(k) for k in ('RURINO_CHAT_PROVIDER', 'RURINO_CHAT_MODEL')}
        os.environ['RURINO_CHAT_PROVIDER'] = 'deepseek'
        os.environ['RURINO_CHAT_MODEL'] = 'deepseek-chat'
        try:
            backend = config_module.ChatBackend.load()
            self.assertEqual(backend.provider, 'deepseek')
            self.assertEqual(backend.chat_url, 'https://api.deepseek.com/v1/chat/completions')
            self.assertEqual(backend.key_env, 'RURINO_DEEPSEEK_KEY')
        finally:
            for key, value in old.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    def test_check_flags_missing_deepseek_key(self):
        old = os.environ.pop('RURINO_DEEPSEEK_KEY', None)
        try:
            cfg = config_module.Config(chat=config_module.ChatBackend(
                provider='deepseek', base='https://api.deepseek.com',
                model='deepseek-chat', path='/v1/chat/completions',
                key_env='RURINO_DEEPSEEK_KEY'))
            self.assertTrue(any('RURINO_DEEPSEEK_KEY' in item for item in cfg.check()))
        finally:
            if old is not None:
                os.environ['RURINO_DEEPSEEK_KEY'] = old


if __name__ == '__main__':
    unittest.main()
