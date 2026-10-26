"""Loopback-only persistent Japanese TTS and local Whisper ASR service."""
import argparse
import io
import json
import logging
import os
from pathlib import Path
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit
import wave


class SpeechEngine:
    def __init__(self, assets, device='cpu', whisper_model='base'):
        self.assets = Path(assets).resolve()
        self.device = device
        self.whisper_model = whisper_model
        self.tts = None
        self.asr = None
        self.lock = threading.Lock()

    def load_tts(self):
        if self.tts is not None:
            return
        root = self.assets
        os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
        import torch
        from style_bert_vits2.constants import Languages
        from style_bert_vits2.nlp import bert_models
        from style_bert_vits2.tts_model import TTSModel
        torch.set_num_threads(2)
        folder = root / 'model_assets/speaker_1'
        bert = root / 'bert/deberta-v2-large-japanese-char-wwm'
        for path in (folder / 'speaker_1_e24_s25000.safetensors', bert / 'pytorch_model.bin'):
            if not path.is_file() or path.stat().st_size < 1_000_000:
                raise ValueError('语音权重未下载完整，请运行 speech/download_assets.py 或 git lfs pull。')
        bert_models.load_tokenizer(Languages.JP, str(bert))
        bert_models.load_model(Languages.JP, str(bert), device_map=self.device)
        self.tts = TTSModel(model_path=folder / 'speaker_1_e24_s25000.safetensors',
                            config_path=folder / 'config.json', style_vec_path=folder / 'style_vectors.npy',
                            device=self.device)

    def synthesize(self, text):
        import numpy as np
        import soundfile as sf
        import torch
        from style_bert_vits2.constants import Languages
        with self.lock:
            self.load_tts()
            with torch.inference_mode():
                rate, audio = self.tts.infer(text=text, language=Languages.JP, speaker_id=0,
                    reference_audio_path=None, style='Neutral', style_weight=1.,
                    sdp_ratio=.3, noise=.05, noise_w=.05, length=1., line_split=True,
                    split_interval=.25, pitch_scale=1., intonation_scale=1.)
            if audio.ndim != 1 or not len(audio) or not np.isfinite(audio).all():
                raise ValueError('合成音频无效。')
            out = io.BytesIO()
            sf.write(out, audio, rate, format='WAV', subtype='PCM_16')
            return out.getvalue()

    def transcribe(self, data, language):
        import numpy as np
        import soundfile as sf
        with wave.open(io.BytesIO(data), 'rb') as stream:
            if (stream.getsampwidth() != 2 or stream.getnchannels() not in (1, 2)
                    or stream.getframerate() < 8000 or stream.getnframes() / stream.getframerate() > 35):
                raise ValueError('录音需要不超过 35 秒的 16 位 PCM WAV。')
        audio, _ = sf.read(io.BytesIO(data))
        if not len(audio) or np.sqrt(np.mean(audio ** 2)) < .0005:
            return ''
        with self.lock:
            if self.asr is None:
                from faster_whisper import WhisperModel
                self.asr = WhisperModel(self.whisper_model, device='cpu', compute_type='int8', cpu_threads=2)
            segments, _ = self.asr.transcribe(io.BytesIO(data), language=language or None,
                                               beam_size=1, condition_on_previous_text=False)
            return ''.join(segment.text for segment in segments).strip()


def make_handler(engine):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            logging.info(fmt, *args)

        def respond(self, status, data, kind='application/json'):
            if kind == 'application/json':
                data = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(data)

        def allowed(self):
            host = urlsplit('http://' + self.headers.get('Host', '')).hostname
            return host in ('localhost', '127.0.0.1', '::1') and not self.headers.get('Origin')

        def do_GET(self):
            if not self.allowed():
                return self.respond(403, {'error': 'Local application requests only.'})
            if self.path == '/health':
                return self.respond(200, {'service': 'rurino-speech', 'tts_loaded': engine.tts is not None,
                                           'asr_loaded': engine.asr is not None, 'device': engine.device})
            self.respond(404, {'error': 'Unknown endpoint'})

        def do_POST(self):
            try:
                if not self.allowed():
                    return self.respond(403, {'error': 'Local application requests only.'})
                length = int(self.headers.get('Content-Length', '0'))
                if length <= 0 or length > 8_000_000:
                    return self.respond(413, {'error': 'Invalid request size'})
                self.connection.settimeout(30)
                body = self.rfile.read(length)
                if len(body) != length:
                    raise ValueError('Incomplete request')
                if self.path == '/tts':
                    text = json.loads(body).get('text')
                    if not isinstance(text, str) or not text.strip() or len(text) > 160:
                        raise ValueError('TTS text must contain 1–160 characters')
                    return self.respond(200, engine.synthesize(text.strip()), 'audio/wav')
                if self.path == '/transcribe':
                    language = self.headers.get('X-Speech-Language', '')
                    if language not in ('', 'zh', 'ja', 'en'):
                        raise ValueError('Unsupported language')
                    return self.respond(200, {'text': engine.transcribe(body, language)})
                self.respond(404, {'error': 'Unknown endpoint'})
            except (BrokenPipeError, ConnectionResetError):
                pass
            except (ValueError, TypeError, wave.Error) as error:
                self.respond(400, {'error': str(error)})
            except Exception as error:
                logging.exception('Speech request failed')
                self.respond(500, {'error': str(error)})
    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--assets', type=Path, default=Path(__file__).resolve().parents[1] / '.voice-assets')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--device', choices=['cpu', 'cuda'], default='cpu')
    parser.add_argument('--whisper-model', default='base')
    parser.add_argument('--warm', action='store_true')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    engine = SpeechEngine(args.assets, args.device, args.whisper_model)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(engine))
    if args.warm:
        def warm():
            try:
                engine.synthesize('こんにちは。')
                print('Voice model ready.', flush=True)
            except Exception:
                logging.exception('Voice warm-up failed; check assets and dependencies')
        threading.Thread(target=warm, daemon=True).start()
    print(f'Local speech service: http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
