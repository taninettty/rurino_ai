"""Ollama / OpenAI 兼容后端的传输层（默认本地，不自动降级到云端）。

设计：
- `stream_reply` / `translate_reply` 接受可选 `backend`；不传时按
  `RURINO_CHAT_PROVIDER` 决定走本地 Ollama 还是远程兼容端点。
- 本地路径保留原来的一切校验（只允许环回地址、禁跳转、禁代理），
  因为本地提示词不该被静默转发出去。
- 远程路径交给 `chat_openai`，它负责 SSE 与鉴权。
"""
import config as config_module
import chat_openai
import io
import json
import queue
import re
import threading
from dataclasses import replace
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
import wave

SYSTEM_PROMPT = ('你是用户桌面上的瑠璃乃角色陪伴助手，开朗、自然、体贴。'
                 '用户可以用中文或日语提问。因为配音模型只支持日语，你的回答必须是自然日语，'
                 '通常一到三句，尽量简短。不要输出思考过程、Markdown、括号动作或表情符号。'
                 '不声称自己是官方人物本人或真人声优。遇到不知道的事情坦诚说明。')

TRANSLATE_PROMPT = ('你是日语到简体中文的翻译。把用户发来的日语译成自然、口语的简体中文。'
                    '只输出译文本身：不要解释、不要保留日文、不要加引号、括号或说话人名字。')

KANA = re.compile(r'[\u3040-\u30ff]')
CHINESE = re.compile(r'[\u4e00-\u9fff]')
MAX_REPLY = 2400


def backend_for(base=None, model=None):
    """按配置决定后端；本地模式下允许 UI 覆盖地址与模型。"""
    cfg = config_module.ChatBackend.load()
    if cfg.provider == 'ollama':
        return replace(cfg, base=base or cfg.base, model=model or cfg.model)
    return cfg


def local_url(value):
    value = value.strip().rstrip('/')
    parsed = urlsplit(value)
    if (parsed.scheme != 'http' or parsed.hostname not in ('localhost', '127.0.0.1', '::1')
            or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment):
        raise ValueError('本地服务地址应为 http://127.0.0.1:端口 或 localhost，不支持云端地址。')
    _ = parsed.port
    return value


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('本地服务意外重定向，已停止请求。')


def request(base, endpoint, data=None, content_type='application/json', timeout=120, headers=None):
    url = local_url(base) + endpoint
    req = Request(url, data=data, headers={'Content-Type': content_type, **(headers or {})})
    # 本地提示词不能走系统代理，否则可能被转发到外部。
    return build_opener(ProxyHandler({}), NoRedirect()).open(req, timeout=timeout)


def get_json(base, endpoint):
    with request(base, endpoint, timeout=5) as response:
        body = response.read(2_000_001)
    if len(body) > 2_000_000:
        raise ValueError('本地服务响应过大。')
    return json.loads(body)


def _stream_openai(backend, messages, cancelled):
    """把回调式客户端转成生成器：工作线程推块，主线程按需取。"""
    pending = queue.Queue()
    done = threading.Event()
    error = {}

    def worker():
        try:
            chat_openai.stream_chat(backend, messages,
                                    on_delta=pending.put, cancel=cancelled)
        except Exception as problem:          # 交给消费端抛出
            error['value'] = problem
        finally:
            done.set()

    threading.Thread(target=worker, daemon=True).start()
    count = 0
    while not done.is_set() or not pending.empty():
        if cancelled.is_set():
            return
        try:
            piece = pending.get(timeout=0.1)
        except queue.Empty:
            continue
        count += len(piece)
        if count > MAX_REPLY:
            raise ValueError('回复过长，请要求简短回答。')
        yield piece
    if 'value' in error:
        raise error['value']


def stream_reply(base, model, messages, cancelled, backend=None):
    backend = backend or backend_for(base, model)
    if backend.provider != 'ollama':
        yield from _stream_openai(backend, messages, cancelled)
        return

    payload = {'model': backend.model, 'messages': messages, 'stream': True, 'think': False,
               'options': {'temperature': .7, 'num_predict': 220, 'num_ctx': 2048}}
    with request(backend.base, '/api/chat', json.dumps(payload).encode()) as response:
        count = 0
        complete = False
        while not cancelled.is_set():
            line = response.readline(65537)
            if not line:
                break
            if len(line) > 65536:
                raise ValueError('Ollama 返回的数据行过长。')
            item = json.loads(line)
            if item.get('error'):
                raise RuntimeError(str(item['error']))
            chunk = item.get('message', {}).get('content', '')
            if not isinstance(chunk, str):
                raise ValueError('Ollama 返回的回复格式不正确。')
            count += len(chunk)
            if count > MAX_REPLY:
                raise ValueError('回复过长，请要求简短回答。')
            if chunk and not cancelled.is_set():
                yield chunk
            if item.get('done'):
                complete = True
                break
        if not complete and not cancelled.is_set():
            raise RuntimeError('Ollama 连接提前结束，请重试。')


class Sentences:
    def __init__(self):
        self.pending = ''

    def feed(self, text, final=False):
        self.pending += text
        ready = []
        while self.pending:
            match = re.search(r'[。！？!?\n]', self.pending)
            if match and match.end() <= 120:
                cut = match.end()
            elif len(self.pending) >= 120:
                cut = 120
            elif final:
                cut = len(self.pending)
            else:
                break
            sentence = self.pending[:cut].strip()
            self.pending = self.pending[cut:]
            if sentence and any(char.isalnum() for char in sentence):
                ready.append(sentence)
        return ready


def translate_reply(base, model, text, cancelled, backend=None):
    """第二次调用，把日语回复译成中文字幕；不合格就返回空，不硬凑。"""
    if cancelled.is_set():
        return ''
    backend = backend or backend_for(base, model)
    messages = [{'role': 'system', 'content': TRANSLATE_PROMPT},
                {'role': 'user', 'content': text}]
    if backend.provider != 'ollama':
        content = chat_openai.complete(backend, messages)
        return clean_translation(content)

    payload = {'model': backend.model, 'stream': False, 'think': False,
               'messages': messages,
               'options': {'temperature': .2, 'num_predict': 260, 'num_ctx': 2048}}
    with request(backend.base, '/api/chat', json.dumps(payload).encode(), timeout=60) as response:
        body = response.read(2_000_001)
    if len(body) > 2_000_000:
        raise ValueError('本地服务响应过大。')
    item = json.loads(body)
    if item.get('error'):
        raise RuntimeError(str(item['error']))
    content = item.get('message', {}).get('content', '')
    if not isinstance(content, str):
        raise ValueError('Ollama 返回的译文格式不正确。')
    return clean_translation(content)


def clean_translation(value):
    """规范化译文，并拒绝"把日文当译文"的情况。"""
    text = ' '.join(value.split()).strip(' "\'“”「」『』')
    if not text:
        raise ValueError('没有拿到中文译文。')
    if not CHINESE.search(text):
        raise ValueError('模型没有返回中文译文。')
    if len(KANA.findall(text)) > len(text) * .3:
        raise ValueError('模型把日文原文当成了译文。')
    return text[:300]


def speech(base, text):
    with request(base, '/tts', json.dumps({'text': text}).encode()) as response:
        data = response.read(12_000_001)
    if len(data) > 12_000_000:
        raise ValueError('合成音频过大。')
    with wave.open(io.BytesIO(data), 'rb') as stream:
        if (stream.getnchannels() != 1 or stream.getsampwidth() != 2 or
                stream.getframerate() < 8000 or stream.getnframes() / stream.getframerate() > 60):
            raise ValueError('语音服务未返回可播放的单声道 PCM WAV。')
    return data


def transcribe(base, wav, language):
    with request(base, '/transcribe', wav, 'audio/wav', headers={'X-Speech-Language': language}) as response:
        result = json.loads(response.read(65536))
    text = result.get('text', '').strip()
    if not text:
        raise ValueError('没有识别到说话内容，请靠近麦克风再试。')
    return text
