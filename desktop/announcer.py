"""播报队列：分句 → 逐句合成 → 顺序播放 → 字幕回调。

分工：
- 工作线程只做 TTS（网络/GPU），不碰 Qt 对象；
- GUI 线程用 QTimer 顺序播放，保证嘴型取样与播放同线程；
- 停止 = 不再排下一句，**当前句播完即停**（符合 VOICE.md 的打断要求）。

首句延迟从 say() 被调用算起，到第一段音频真正开始播放为止。
"""
from collections import deque
import tempfile
import threading
import time
from pathlib import Path
import uuid

from PyQt5.QtCore import QObject, QTimer, pyqtSignal

from say import split


class Announcer(QObject):
    changed = pyqtSignal(str, object)          # ('subtitle'|'state'|'error', payload)

    def __init__(self, voice, synthesize, parent=None):
        super().__init__(parent)
        self.voice = voice
        self.synthesize = synthesize          # (text) -> wav bytes
        self.audio = deque()
        self.tmp = tempfile.TemporaryDirectory(prefix='rurino-say-', ignore_cleanup_errors=True)
        self.current = None
        self.cancelled = threading.Event()
        self.started_at = None
        self.first_play_at = None
        self.last_latency = None
        self.pending = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(50)

    # --- 对外 -------------------------------------------------------------
    def say(self, ja_text, zh_text=''):
        """播报一段话；返回分句数量，0 表示没有可播内容。"""
        sentences = split(ja_text)
        self.zh_text = zh_text or ''
        if not sentences:
            return 0
        self.stop()
        self.cancelled = threading.Event()
        cancelled = self.cancelled
        self.started_at = time.monotonic()
        self.first_play_at = None
        self.pending = len(sentences)
        self.changed.emit('state', 'speaking')
        threading.Thread(target=self._work, args=(sentences, zh_text, cancelled), daemon=True).start()
        return len(sentences)

    def stop(self):
        """停止排队：当前句播完不再继续。"""
        self.cancelled.set()
        self.audio.clear()
        self.pending = 0
        if self.first_play_at is None:
            self.started_at = None

    def idle(self):
        return not self.audio and self.pending == 0 and not self.voice.playing()

    # --- 工作线程 ---------------------------------------------------------
    def _work(self, sentences, zh_text, cancelled):
        for index, sentence in enumerate(sentences, 1):
            if cancelled.is_set():
                return
            try:
                data = self.synthesize(sentence)
            except Exception as error:
                if not cancelled.is_set():
                    self.changed.emit('error', f'合成失败：{error}')
                    self.pending = 0
                return
            if cancelled.is_set():
                return
            self.audio.append((index, len(sentences), sentence, data))
            self.pending = max(0, self.pending - 1)

    # --- GUI 线程 ---------------------------------------------------------
    def _tick(self):
        if self.voice.playing() or not self.audio:
            return
        index, total, sentence, data = self.audio.popleft()
        path = Path(self.tmp.name) / f'{uuid.uuid4().hex}.wav'
        try:
            path.write_bytes(data)
            self.voice.load(path)
            self.voice.play()
        except Exception as error:
            self.changed.emit('error', f'播放失败：{error}')
            return
        if self.current:
            self._remove(self.current)
        self.current = path
        if self.first_play_at is None:
            self.first_play_at = time.monotonic()
            self.last_latency = self.first_play_at - self.started_at
        self.changed.emit('subtitle', {'index': index, 'total': total, 'ja': sentence,
                                     'zh': getattr(self, 'zh_text', '') if total == 1 else ''})
        if not self.audio:
            self.changed.emit('state', 'idle')

    @staticmethod
    def _remove(path):
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            pass

    def shutdown(self):
        self.stop()
        self.timer.stop()
        self.voice.stop()
        if self.current:
            self._remove(self.current)
        self.tmp.cleanup()
