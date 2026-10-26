"""Deterministic protocol double; does not stand in for an Ollama quality test."""
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import threading
import time
import wave


def wav_bytes():
    out = io.BytesIO()
    with wave.open(out, 'wb') as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16000)
        stream.writeframes(b'\x01\x10' * 1600)
    return out.getvalue()


@contextmanager
def protocol_server():
    requests = []
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, data, kind='application/json'):
            self.send_response(200)
            self.send_header('Content-Type', kind)
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            data = {'models': [{'name': 'test-local'}]} if self.path == '/api/tags' else {'service': 'rurino-speech', 'tts_loaded': True}
            self.reply(json.dumps(data).encode())

        def do_POST(self):
            raw = self.rfile.read(int(self.headers['Content-Length']))
            if self.path == '/tts':
                requests.append(('tts', json.loads(raw)))
                self.reply(wav_bytes(), 'audio/wav')
            elif self.path == '/transcribe':
                requests.append(('asr', len(raw)))
                self.reply(json.dumps({'text': '今天好吗？'}).encode())
            else:
                body = json.loads(raw)
                requests.append(('chat', body))
                mode = body['messages'][-1]['content']
                if mode == 'retry-once' and sum(1 for kind, body in requests if kind == 'chat' and body['messages'][-1]['content'] == mode) == 1:
                    self.send_response(503)
                    self.end_headers()
                    self.wfile.write(b'{"error":"temporarily unavailable"}')
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'application/x-ndjson')
                self.end_headers()
                chunks = ['今日は', '元気だよ。', 'お話ししよう！']
                try:
                    for chunk in chunks:
                        self.wfile.write((json.dumps({'message': {'content': chunk, 'thinking': 'hidden'}}, ensure_ascii=False)+'\n').encode())
                        self.wfile.flush()
                        time.sleep(.3 if mode == 'slow' else .02)
                    if mode != 'incomplete':
                        self.wfile.write(b'{"done":true}\n')
                except (BrokenPipeError, ConnectionResetError):
                    pass
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', requests
    finally:
        server.shutdown()
        server.server_close()
