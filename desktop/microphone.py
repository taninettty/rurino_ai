"""Explicit start/stop microphone recording; no background listening."""
import io
import wave

from PyQt5.QtCore import QByteArray, QBuffer, QIODevice
from PyQt5.QtMultimedia import QAudioDeviceInfo, QAudioFormat, QAudioInput


class Microphone:
    def __init__(self, parent):
        self.parent = parent
        self.audio = None

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
        self.buffer = QBuffer(self.bytes, self.parent)
        self.buffer.open(QIODevice.WriteOnly)
        self.audio = QAudioInput(device, fmt, self.parent)
        self.audio.start(self.buffer)
        if self.audio.error():
            self.stop()
            raise RuntimeError('无法打开麦克风，请检查麦克风权限或设备占用。')

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
        if not raw:
            return b''
        out = io.BytesIO()
        with wave.open(out, 'wb') as stream:
            stream.setnchannels(self.format.channelCount())
            stream.setsampwidth(2)
            stream.setframerate(self.format.sampleRate())
            stream.writeframes(raw)
        return out.getvalue()
