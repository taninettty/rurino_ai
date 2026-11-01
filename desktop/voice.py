"""Playback + amplitude envelope for lip sync.

QMediaPlayer (WMF on Windows) replaces winsound: it gives a real playback
position, a volume control and a stop that cannot swallow other sounds.
Winsound could not report where it was, so the mouth used a stopwatch and
drifted out of sync on slow disks.
"""
import array
import math
import sys
import time
import wave

from PyQt5.QtCore import QUrl
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer


class Voice:
    def __init__(self, path, parent=None):
        self.player = QMediaPlayer(parent)
        self.player.setVolume(70)
        self.started = None
        self.path = None
        self.duration = 0.0
        self.step = 0.02
        self.envelope = []
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
        self.player.setMedia(QMediaContent(QUrl.fromLocalFile(str(path))))

    def play(self):
        self.stop()
        self.player.setPosition(0)
        self.player.play()
        self.started = time.monotonic()

    def playing(self):
        return self.player.state() == QMediaPlayer.PlayingState

    def position(self):
        """Playback position in seconds; the media player reports milliseconds."""
        return self.player.position() / 1000.0

    def mouth(self):
        if not self.playing():
            return 0.0
        index = int(self.position() / self.step)
        return self.envelope[index] if index < len(self.envelope) else 0.0

    def set_volume(self, percent):
        self.player.setVolume(max(0, min(100, int(percent))))

    def stop(self):
        self.player.stop()
        self.started = None