"""瑠璃乃的说话方式（唯一来源）。

依据：游戏卡面语音 451 行（irodori-drop リンクラ 大沢瑠璃乃 カード・ボイス一覧）。
反复出现的特征：
- 自称「ルリ」（第三人称自称）
- 句尾「〜っしょ」「〜っす」
- 拉长音表示兴奋（まーた、すげー、だー）
- 感叹词（おっしゃー！、ほいっ、さいっこー）
- 对慈叫「めぐちゃん」

这里只放"怎么说话"的规则，不放官方台词原文。
"""
import re

SELF = 'ルリ'
DEFAULT_CALL = 'あなた'

TICS = ('っしょ', 'っす', 'だよ', 'だね', 'かな')
EXCLAMATIONS = ('おっしゃー', 'ほいっ', 'さいっこー', 'やったー')
MAX_SENTENCES = 2

# 出现即 OOC：助手腔、敬语腔、书面语
FORBIDDEN = ('作为一个ai', '我建议您', '申し上げます', 'でございます', 'いたします',
             'please note', 'as an ai', '抱歉，我无法')

LONG_VOWEL = re.compile(r'[ぁ-んァ-ン]ー')


def style_prompt():
    """给 LLM 的改写约束：只换说法，不改人物。"""
    return ('你是日语改写助手。把句子改成同一个角色的口吻：自称「ルリ」，'
            '句尾常用「〜っしょ」「〜っす」，语气轻快、爱开玩笑。'
            '必须保留原句全部数字与专有名词，不增删事实，不要写成敬语或客服腔。')


def check(text, quoted=False):
    """返回 (是否贴合, 原因)。

    quoted=True 用于游戏原句：原句的出处就是证据，不再要求它带自称或口癖
    （真实台词里有大量「行こうよ！みんなで！」这类不含标记的句子）。
    生成的新句仍走 quoted=False，必须带标记，避免跑偏成通用助手腔。
    """
    if not text or not text.strip():
        return False, '空文本'
    lowered = text.lower()
    for word in FORBIDDEN:
        if word.lower() in lowered:
            return False, f'出现助手腔/敬语：{word}'
    sentences = [s for s in re.split(r'[。！？!?\n]', text) if s.strip()]
    if len(sentences) > MAX_SENTENCES:
        return False, f'句子过多（{len(sentences)} > {MAX_SENTENCES}）'
    if quoted:
        return True, 'ok'
    marked = SELF in text or any(tic in text for tic in TICS) or any(word in text for word in EXCLAMATIONS)
    if not marked:
        return False, '缺少自称「ルリ」或口癖'
    return True, 'ok'


def ensure(text, fallback):
    """台词不贴合时退回一个已确认贴合的句子，绝不把 OOC 文本播出去。"""
    ok, _reason = check(text)
    return text if ok else fallback
