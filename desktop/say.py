"""播报文本：模板渲染 + LLM 润色 + 事实校验 + 分句。

规则（见 desktop/VOICE.md）：
- 模板负责事实（时间、数字），由程序填；
- LLM 只做同义改写，**不得改动任何数字、时间、专名**；
- 改写结果必须包含原文里的全部数字，否则回退模板原文；
- 分句交给 chat_client.Sentences，与 TTS 链路保持一致。
"""
import re

from chat_client import Sentences
import persona

TEMPLATES = [
    {'id': 'morning',
     'ja': 'おはよう！今は{hour}時だよ、ルリと一緒にがんばろっしょ。',
     'zh': '早上好，现在是 {hour} 点。今天也一起加油吧。'},
    {'id': 'day',
     'ja': 'こんにちは！今は{hour}時、ちょっと休憩しよーっす。',
     'zh': '你好，现在是 {hour} 点。要不要聊两句？'},
    {'id': 'evening',
     'ja': 'こんばんは、{hour}時だね。今日もおつかれーっしょ。',
     'zh': '晚上好，已经 {hour} 点了。今天过得怎么样？'},
]

POLISH_PROMPT = persona.style_prompt()

NUMBER = re.compile(r'[0-9０-９]+')


def pick_template(hour):
    """按时段选模板：5-10 早上，11-17 白天，其余晚上。"""
    hour = int(hour) % 24
    if 5 <= hour < 11:
        return TEMPLATES[0]
    if 11 <= hour < 18:
        return TEMPLATES[1]
    return TEMPLATES[2]


def render(template, hour):
    """填充事实槽位，返回日文与中文字幕两条。"""
    hour = int(hour) % 24
    return {'id': template['id'],
            'ja': template['ja'].format(hour=hour),
            'zh': template['zh'].format(hour=hour)}


def numbers(text):
    """抽出全部数字（含全角），用于判断改写是否篡改事实。"""
    return sorted(NUMBER.findall(text))


def facts_preserved(base, polished):
    """改写后必须包含原句的全部数字；多出数字也算篡改。"""
    if not polished or not polished.strip():
        return False
    return numbers(base) == numbers(polished)


def polish(base_ja, request_text, cancelled=None, max_ratio=1.5):
    """让 LLM 改写；任何异常或校验失败都回退原文，绝不阻塞播报。

    request_text(prompt, text) -> str 由调用方注入，便于测试与替换后端。
    """
    if cancelled is not None and cancelled.is_set():
        return base_ja
    try:
        candidate = request_text(POLISH_PROMPT, base_ja).strip()
    except Exception:
        return base_ja
    if len(candidate) > len(base_ja) * max_ratio:
        return base_ja
    return candidate if facts_preserved(base_ja, candidate) else base_ja


def split(text):
    """按句切分，复用与 TTS 相同的规则（句末标点、最长 120 字）。"""
    splitter = Sentences()
    sentences = splitter.feed(text, final=True)
    return sentences or ([text.strip()] if text.strip() else [])
