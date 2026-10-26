"""Explicit start/stop microphone recording; no background listening."""
import array
import io
import math
import sys
import wave

from PyQt5.QtCore import QByteArray, QBuffer, QIODevice
from PyQt5.QtMultimedia import QAudioDeviceInfo, QAudioFormat, QAudioInput


class Microphone:
    def __init__(self, parent):
        self.parent = parent
        self.audio = None
        self.format = None
        self.read_offset = 0

    def start(self):
        device = QAudioDeviceInfo.defaultInputDevice()
        if device.isNull():
            raise RuntimeError('没有找到麦克风，请检查 Windows 麦克风权限和输入设备。')
        fmt = QAudioFormat()
        fmt.setSampleRate(16000)
        fmt.setChannelCount(1)
        fmt.setSampleSize(16)
        fmt.setCodec('audio/pcm')
        fmt.setByteOrder(QAudioFormat.LittleEndian)
        fmt.setSampleType(QAudioFormat.SignedInt)
        if not device.isFormatSupported(fmt):
            fmt = device.nearestFormat(fmt)
        if (fmt.sampleSize() != 16 or fmt.channelCount() not in (1, 2) or
                fmt.byteOrder() != QAudioFormat.LittleEndian or fmt.sampleType() != QAudioFormat.SignedInt):
            raise RuntimeError('麦克风不支持 16 位 PCM，请在系统声音设置中更换输入格式。')
        self.format = fmt
        self.bytes = QByteArray()
        self.read_offset = 0
        self.buffer = QBuffer(self.bytes, self.parent)
        self.buffer.open(QIODevice.WriteOnly)
        self.audio = QAudioInput(device, fmt, self.parent)
        self.audio.start(self.buffer)
        if self.audio.error():
            self.stop()
            raise RuntimeError('无法打开麦克风，请检查麦克风权限或设备占用。')

    def level(self):
        """RMS amplitude (0..1) of the audio captured since the previous call.

        Reading consumes the samples conceptually only: the full buffer is still
        written out by :meth:`stop`, so callers may poll this while recording.
        """
        if self.audio is None or self.format is None:
            return 0.0
        frame = 2 * self.format.channelCount()
        end = self.bytes.size()
        end -= (end - self.read_offset) % frame
        if end <= self.read_offset:
            return 0.0
        block = bytes(self.bytes.mid(self.read_offset, end - self.read_offset))
        self.read_offset = end
        samples = array.array('h', block)
        if sys.byteorder != 'little':
            samples.byteswap()
        if not samples:
            return 0.0
        return min(1.0, math.sqrt(sum(value * value for value in samples) / len(samples)) / 32768)

    def stop(self):
        if self.audio is None:
            return b''
        self.audio.stop()
        self.audio.deleteLater()
        self.audio = None
        self.buffer.close()
        raw = bytes(self.bytes)
        self.buffer.deleteLater()
        frame = 2 * self.format.channelCount()
        raw = raw[:len(raw) // frame * frame]
        self.read_offset = 0
        if not raw:
            return b''
        out = io.BytesIO()
        with wave.open(out, 'wb') as stream:
            stream.setnchannels(self.format.channelCount())
            stream.setsampwidth(2)
            stream.setframerate(self.format.sampleRate())
            stream.writeframes(raw)
        return out.getvalue()
