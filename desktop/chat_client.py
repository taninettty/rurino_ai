"""Local Ollama streaming and local speech service transport (no cloud fallback)."""
import io
import json
import re
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler
import wave

SYSTEM_PROMPT = ('你是用户桌面上的瑠璃乃角色陪伴助手，开朗、自然、体贴。'
                 '用户可以用中文或日语提问。因为配音模型只支持日语，你的回答必须是自然日语，'
                 '通常一到三句，尽量简短。不要输出思考过程、Markdown、括号动作或表情符号。'
                 '不声称自己是官方人物本人或真人声优。遇到不知道的事情坦诚说明。')

# The voice model only accepts Japanese, so the subtitle is a second local pass
# instead of asking the conversation model for two languages at once.
TRANSLATE_PROMPT = ('你是日语到简体中文的翻译。把用户发来的日语译成自然、口语的简体中文。'
                    '只输出译文本身：不要解释、不要保留日文、不要加引号、括号或说话人名字。')

KANA = re.compile(r'[\u3040-\u30ff]')
CHINESE = re.compile(r'[\u4e00-\u9fff]')


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
    # Local prompts must not be routed through configured HTTP proxies.
    return build_opener(ProxyHandler({}), NoRedirect()).open(req, timeout=timeout)


def get_json(base, endpoint):
    with request(base, endpoint, timeout=5) as response:
        body = response.read(2_000_001)
    if len(body) > 2_000_000:
        raise ValueError('本地服务响应过大。')
    return json.loads(body)


def stream_reply(base, model, messages, cancelled):
    payload = {'model': model, 'messages': messages, 'stream': True, 'think': False,
               'options': {'temperature': .7, 'num_predict': 220, 'num_ctx': 2048}}
    with request(base, '/api/chat', json.dumps(payload).encode()) as response:
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
            if count > 2400:
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


def translate_reply(base, model, text, cancelled):
    """Second local pass that turns the Japanese reply into a Chinese subtitle.

    It runs after the streamed answer so the conversation stays as fast as the
    model, and it never accepts output that is empty, untranslated or not
    Chinese, because a wrong subtitle is worse than a missing one.
    """
    if cancelled.is_set():
        return ''
    payload = {'model': model, 'stream': False, 'think': False,
               'messages': [{'role': 'system', 'content': TRANSLATE_PROMPT},
                            {'role': 'user', 'content': text}],
               'options': {'temperature': .2, 'num_predict': 260, 'num_ctx': 2048}}
    with request(base, '/api/chat', json.dumps(payload).encode(), timeout=60) as response:
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
    """Normalise a translated subtitle and reject Japanese passed through."""
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
