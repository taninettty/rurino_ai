from pathlib import Path
import sys
import threading
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from chat_client import local_url, Sentences, stream_reply, speech, transcribe
from speech.server import make_handler
from http.server import ThreadingHTTPServer
from protocol_fixture import protocol_server, wav_bytes


class ChatProtocolTests(unittest.TestCase):
    def test_loopback_only(self):
        self.assertEqual(local_url('http://localhost:11434/'), 'http://localhost:11434')
        for value in ['https://example.com', 'http://127.0.0.1.evil.test', 'http://user:pw@localhost',
                      'http://localhost/path', 'http://localhost?cloud=1', 'file:///tmp/x']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                local_url(value)

    def test_sentence_fragments_and_bounded_long_output(self):
        splitter = Sentences()
        self.assertEqual(splitter.feed('こん'), [])
        self.assertEqual(splitter.feed('にちは。次'), ['こんにちは。'])
        self.assertEqual(splitter.feed('', final=True), ['次'])
        self.assertEqual([len(x) for x in splitter.feed('あ'*260, final=True)], [120, 120, 20])
        self.assertEqual(splitter.feed('！\n', final=True), [])

    def test_streamed_text_context_and_wav(self):
        with protocol_server() as (base, requests):
            text = ''.join(stream_reply(base, 'test-local', [{'role': 'user', 'content': 'hi'}], threading.Event()))
            self.assertEqual(text, '今日は元気だよ。お話ししよう！')
            self.assertEqual(speech(base, 'こんにちは。'), wav_bytes())
            self.assertEqual(transcribe(base, wav_bytes(), 'zh'), '今天好吗？')
            self.assertFalse(requests[0][1]['think'])

    def test_incomplete_response_is_not_success(self):
        with protocol_server() as (base, _):
            with self.assertRaisesRegex(RuntimeError, '提前结束'):
                list(stream_reply(base, 'test-local', [{'role': 'user', 'content': 'incomplete'}], threading.Event()))

    def test_cancel_stops_chunks(self):
        with protocol_server() as (base, _):
            cancel = threading.Event()
            chunks = stream_reply(base, 'test-local', [{'role': 'user', 'content': 'slow'}], cancel)
            self.assertEqual(next(chunks), '今日は')
            cancel.set()
            self.assertEqual(list(chunks), [])

    def test_voice_server_rejects_browser_and_oversize(self):
        class Engine:
            tts = asr = None
            device = 'cpu'
        server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(Engine()))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = f'http://127.0.0.1:{server.server_port}'
        try:
            with self.assertRaises(HTTPError) as caught:
                urlopen(Request(base+'/health', headers={'Origin': 'https://example.com'}))
            self.assertEqual(caught.exception.code, 403)
            with self.assertRaises(HTTPError) as caught:
                urlopen(Request(base+'/tts', data=b'{}', headers={'Content-Length': '9000000'}))
            self.assertEqual(caught.exception.code, 413)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
