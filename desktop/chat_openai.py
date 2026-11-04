"""OpenAI 兼容的流式聊天客户端（DeepSeek / 任何兼容端点）。

只负责协议差异：Ollama 走 `/api/chat` 自有 JSON 行，DeepSeek 走
`/v1/chat/completions` + SSE。后端配置统一由 `config.ChatBackend` 提供，
这里不再定义第二份，避免两处参数各写一半。
"""
import json
import urllib.request


class MissingKey(Exception):
    pass


def _payload(backend, messages, stream, temperature=0.8, max_tokens=400):
    body = {
        'model': backend.model,
        'messages': messages,
        'stream': stream,
        'temperature': temperature,
    }
    if backend.provider == 'ollama':
        body['options'] = {'num_predict': max_tokens}
    else:
        body['max_tokens'] = max_tokens
    return json.dumps(body, ensure_ascii=False).encode('utf-8')


def _headers(backend):
    headers = {'Content-Type': 'application/json'}
    if backend.key_env:
        key = backend.api_key()
        if not key:
            raise MissingKey(f'缺少环境变量 {backend.key_env}')
        headers['Authorization'] = f'Bearer {key}'
    return headers


def _delta_from(backend, chunk):
    """从一块 JSON 里取出增量文本；取不到返回空串。"""
    if not chunk:
        return ''
    if backend.provider == 'ollama':
        return (chunk.get('message') or {}).get('content', '') or ''
    choices = chunk.get('choices') or []
    if not choices:
        return ''
    return (choices[0].get('delta') or {}).get('content', '') or ''


def stream_chat(backend, messages, on_delta=None, timeout=60, cancel=None):
    """逐块回调，返回完整文本。网络/协议错误直接抛出，由调用方降级。"""
    request = urllib.request.Request(
        backend.chat_url,
        data=_payload(backend, messages, stream=True),
        headers=_headers(backend),
        method='POST',
    )
    parts = []
    with urllib.request.urlopen(request, timeout=timeout) as response:
        for raw in response:
            if cancel is not None and cancel.is_set():
                break
            line = raw.decode('utf-8', errors='replace').strip()
            if not line or line.startswith(':'):
                continue
            if line.startswith('data:'):
                line = line[5:].strip()
            if line in ('[DONE]', 'done'):
                break
            try:
                chunk = json.loads(line)
            except json.JSONDecodeError:
                continue
            if chunk.get('error'):
                raise RuntimeError(str(chunk['error'])[:200])
            piece = _delta_from(backend, chunk)
            if piece:
                parts.append(piece)
                if on_delta:
                    on_delta(piece)
            if backend.provider == 'ollama' and chunk.get('done'):
                break
    return ''.join(parts)


def complete(backend, messages, timeout=60):
    """非流式一次性取回全文：用于中文字幕翻译这类"只要结果"的调用。

    与 stream_chat 分开是因为服务端对 stream=false 返回单个 JSON，
    再按 SSE 解析会读不到内容（曾因此把日语原文当译文）。
    """
    request = urllib.request.Request(
        backend.chat_url,
        data=_payload(backend, messages, stream=False),
        headers=_headers(backend),
        method='POST',
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read(2_000_001)
    if len(body) > 2_000_000:
        raise ValueError('回复过大。')
    data = json.loads(body.decode('utf-8', errors='replace'))
    if data.get('error'):
        raise RuntimeError(str(data['error'])[:200])
    if backend.provider == 'ollama':
        return (data.get('message') or {}).get('content', '') or ''
    choices = data.get('choices') or []
    if not choices:
        return ''
    return (choices[0].get('message') or {}).get('content', '') or ''
