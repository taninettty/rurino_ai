"""The user's existing greeting, with an amplitude envelope for lip sync."""
import array
import math
import sys
import time
import wave

from PyQt5.QtCore import QUrl


class Voice:
    def __init__(self, path, parent=None):
        self.started = None
        self.effect = None
        self.pending = False
        if sys.platform != 'win32':
            from PyQt5.QtMultimedia import QSoundEffect
            self.effect = QSoundEffect(parent)
            self.effect.setVolume(.7)
            self.effect.statusChanged.connect(self.audio_ready)
        self.load(path)

    def load(self, path):
        self.stop()
        self.path = path
        with wave.open(str(path), 'rb') as stream:
            if stream.getsampwidth() != 2 or stream.getnchannels() != 1:
                raise ValueError('音频需要 16 位单声道 PCM WAV。')
            rate = stream.getframerate()
            self.duration = stream.getnframes() / rate
            samples = array.array('h', stream.readframes(stream.getnframes()))
            if sys.byteorder != 'little':
                samples.byteswap()
        hop = max(1, rate // 50)
        self.step = hop / rate
        self.envelope = []
        for offset in range(0, len(samples), hop):
            chunk = samples[offset:offset + hop]
            rms = math.sqrt(sum(value * value for value in chunk) / len(chunk))
            self.envelope.append(min(1.0, rms / 6500))
        if self.effect:
            self.effect.setSource(QUrl.fromLocalFile(str(path)))

    def audio_ready(self):
        if not self.pending:
            return
        if self.effect.status() == self.effect.Ready:
            self.pending = False
            self.effect.play()
            self.started = time.monotonic()
        elif self.effect.status() == self.effect.Error:
            self.pending = False

    def play(self):
        self.stop()
        if sys.platform == 'win32':
            import winsound
            winsound.PlaySound(str(self.path), winsound.SND_FILENAME | winsound.SND_ASYNC)
        else:
            self.pending = True
            self.audio_ready()
            return
        self.started = time.monotonic()

    def mouth(self):
        if self.started is None:
            return 0.0
        elapsed = time.monotonic() - self.started
        index = int(elapsed / self.step)
        return self.envelope[index] if 0 <= elapsed < self.duration and index < len(self.envelope) else 0.0

    def playing(self):
        return self.pending or (self.started is not None and time.monotonic() - self.started < self.duration)

    def stop(self):
        if sys.platform == 'win32':
            import winsound
            winsound.PlaySound(None, 0)
        elif self.effect:
            self.effect.stop()
        self.started = None
        self.pending = False
