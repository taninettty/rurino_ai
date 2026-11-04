"""播报调度：决定「什么时候说、说什么」。

原则（来自需求与语料）：
- 不做整点报时：时段问候只在「当天第一次活动」时触发一次；
- 先看状态，再看时间：深夜、久坐、刚回来，都是状态驱动的；
- 宁可不说：全局最小间隔 25 分钟，同一规则当天只响一次；
- 不打断：她正在说话时一律不触发；
- 同一句不连着说两遍。

纯逻辑，不依赖 Qt，便于测试；宿主每 30 秒调一次 `tick()` 即可。
"""
from dataclasses import dataclass, field
from datetime import datetime, time
import json
from pathlib import Path
import random
import re

import persona

LINES = json.loads((Path(__file__).resolve().parent / 'data' / 'rurino-lines.json')
                   .read_text(encoding='utf-8-sig'))['lines']
BY_SCENE = {}
for item in LINES:
    BY_SCENE.setdefault(item['scene'], []).append(item)

MIN_GAP = 25 * 60          # 全局最小间隔（秒）
QUIET_START, QUIET_END = time(2, 0), time(6, 0)
AWAY_SECONDS = 20 * 60     # 离开多久算「出门了」
REST_AFTER = 90 * 60       # 连续活跃多久提醒休息
REST_REPEAT = 60 * 60


@dataclass
class Utterance:
    rule: str
    ja: str
    zh: str
    line_id: str


@dataclass
class Context:
    now: datetime
    idle_seconds: float = 0.0
    active_seconds: float = 0.0
    speaking: bool = False
    last_spoken_at: datetime = None
    spoken_today: set = field(default_factory=set)
    recent_lines: list = field(default_factory=list)
    was_away: bool = False
    rest_count: int = 0


def _quiet(now):
    return QUIET_START <= now.time() < QUIET_END


def pick(scene, recent, rng, max_sentences=None):
    """从场景里挑一句：优先原句，避免与最近说过的重复。

    max_sentences 用于「还要再附一句时间」的场合：只挑一句以内的台词，
    否则加时间就会超过 persona 的两句上限。
    """
    pool = BY_SCENE.get(scene, [])
    if max_sentences is not None:
        fits = [item for item in pool if _sentence_count(item['ja']) <= max_sentences]
        pool = fits or pool
    if not pool:
        return None
    fresh = [item for item in pool if item['ja'] not in recent[-3:]]
    verified = [item for item in fresh if item.get('verified')]
    return rng.choice(verified or fresh or pool)


def _sentence_count(text):
    return len([part for part in re.split(r'[。！？!?\n]', text) if part.strip()])


def with_time(line, now):
    """她的原话 + 一句事实时间；事实由程序填，不交给模型。

    原句本身已经两句时不再附时间——超过 persona 的两句上限会被判不贴合，
    宁可少说一句时间，也不要为凑格式把台词切碎。
    """
    if _sentence_count(line['ja']) >= 2:
        return line['ja'], line['zh']
    ja = f"{line['ja']}今は{now.hour}時だよ。"
    zh = f"{line['zh']}现在是 {now.hour} 点。"
    return ja, zh


class Scheduler:
    def __init__(self, rng=None, min_gap=MIN_GAP):
        self.rng = rng or random.Random()
        self.min_gap = min_gap

    # --- 规则 -------------------------------------------------------------
    def _gap_ok(self, ctx):
        if ctx.last_spoken_at is None:
            return True
        return (ctx.now - ctx.last_spoken_at).total_seconds() >= self.min_gap

    def _welcome(self, ctx):
        if not ctx.was_away or ctx.idle_seconds > 60:
            return None
        if 'welcome' in ctx.spoken_today:
            return None
        line = pick('welcome', ctx.recent_lines, self.rng)
        return line and Utterance('welcome', line['ja'], line['zh'], line['id'])

    def _late_night(self, ctx):
        hour = ctx.now.hour
        if hour not in (23, 0, 1):
            return None
        if 'late_night' in ctx.spoken_today:
            return None
        line = pick('late_night', ctx.recent_lines, self.rng)
        return line and Utterance('late_night', line['ja'], line['zh'], line['id'])

    def _rest(self, ctx):
        due = REST_AFTER + ctx.rest_count * REST_REPEAT
        if ctx.active_seconds < due:
            return None
        if ctx.idle_seconds > 120:      # 人不在，别提醒
            return None
        line = pick('rest', ctx.recent_lines, self.rng)
        return line and Utterance('rest', line['ja'], line['zh'], line['id'])

    def _day_slot(self, ctx):
        hour = ctx.now.hour
        if 5 <= hour < 10:
            slot = 'morning'
        elif 17 <= hour < 22:
            slot = 'evening'
        else:
            return None
        if slot in ctx.spoken_today:
            return None
        line = pick(slot, ctx.recent_lines, self.rng, max_sentences=1)
        if not line:
            return None
        ja, zh = with_time(line, ctx.now)
        return Utterance(slot, ja, zh, line['id'])

    # --- 对外 -------------------------------------------------------------
    def decide(self, ctx):
        if ctx.speaking or _quiet(ctx.now) or not self._gap_ok(ctx):
            return None
        for rule in (self._welcome, self._late_night, self._rest, self._day_slot):
            utterance = rule(ctx)
            if utterance:
                return utterance
        return None

    def tick(self, ctx):
        """宿主调用：决定是否说，并就地更新上下文状态。"""
        utterance = self.decide(ctx)
        if utterance:
            ctx.last_spoken_at = ctx.now
            ctx.spoken_today.add(utterance.rule)
            ctx.recent_lines.append(utterance.ja)
            if utterance.rule == 'rest':
                ctx.rest_count += 1
            ok, reason = persona.check(utterance.ja, quoted=True)
            if not ok:
                return None
        return utterance
