"""Responsive local conversation UI with streaming text and queued speech."""
from collections import deque
import json
from pathlib import Path
import queue
import tempfile
import threading
import uuid
from urllib.error import HTTPError

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QTextCursor
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QComboBox, QPushButton, QPlainTextEdit, QLabel, QCheckBox)

from chat_client import SYSTEM_PROMPT, Sentences, get_json, local_url, speech, stream_reply, transcribe
from microphone import Microphone


def error_text(error):
    if isinstance(error, HTTPError):
        try:
            return str(json.loads(error.read(5000)).get('error', str(error)))
        except Exception:
            pass
    return str(error)


class ChatWindow(QWidget):
    worker_event = pyqtSignal(int, str, object)

    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.settings = controller.settings
        self.voice = controller.voice
        self.turn = 0
        self.cancelled = threading.Event()
        self.speech_cancelled = threading.Event()
        self.last_request = ''
        self.history = []
        self.waiting = 0
        self.generating = False
        self.recognizing = False
        self.audio_queue = deque()
        self.current_audio = None
        self.last_error = ''
        self.temp = tempfile.TemporaryDirectory(prefix='rurino-chat-', ignore_cleanup_errors=True)
        self.tts_jobs = queue.Queue()
        self.worker_event.connect(self.handle_event)
        self.microphone = Microphone(self)
        self.recording = False
        self.setWindowTitle('和瑠璃乃聊天 · 本地 Ollama')
        self.resize(560, 660)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.ollama = QLineEdit(self.settings.value('chat/ollama', 'http://127.0.0.1:11434'))
        self.backend = QLineEdit(self.settings.value('chat/speech', 'http://127.0.0.1:8765'))
        self.model = QComboBox()
        self.model.setEditable(True)
        self.model.setCurrentText(self.settings.value('chat/model', ''))
        self.model.lineEdit().setPlaceholderText('检查连接后选择已安装的模型')
        form.addRow('Ollama 地址', self.ollama)
        form.addRow('聊天模型', self.model)
        form.addRow('本地语音服务', self.backend)
        layout.addLayout(form)
        options = QHBoxLayout()
        self.refresh_button = QPushButton('检查连接 / 刷新模型')
        self.refresh_button.clicked.connect(self.refresh)
        options.addWidget(self.refresh_button)
        self.speak = QCheckBox('用现有音色朗读')
        self.speak.setChecked(self.settings.value('chat/speak', True, type=bool))
        self.speak.toggled.connect(self.speech_changed)
        options.addWidget(self.speak)
        layout.addLayout(options)
        self.services = QLabel('先启动 Ollama 和 Start-Voice-Service.cmd，再检查连接。')
        self.services.setWordWrap(True)
        self.services.setTextFormat(Qt.PlainText)
        layout.addWidget(self.services)
        self.transcript = QPlainTextEdit()
        self.transcript.setReadOnly(True)
        self.transcript.setPlaceholderText('可以中文提问；瑠璃乃用日语回复。聊天记录只保留在本次运行中。')
        layout.addWidget(self.transcript, 1)
        self.input = QLineEdit()
        self.input.setMaxLength(1000)
        self.input.setPlaceholderText('输入想说的话，按 Enter 发送…')
        self.input.returnPressed.connect(self.send)
        layout.addWidget(self.input)
        actions = QHBoxLayout()
        self.send_button = QPushButton('发送')
        self.send_button.clicked.connect(self.send)
        actions.addWidget(self.send_button)
        self.record_button = QPushButton('开始录音')
        self.record_button.clicked.connect(self.record)
        actions.addWidget(self.record_button)
        self.language = QComboBox()
        self.language.addItem('中文识别', 'zh')
        self.language.addItem('日语识别', 'ja')
        self.language.addItem('自动识别', '')
        actions.addWidget(self.language)
        stop = QPushButton('打断')
        stop.clicked.connect(self.interrupt)
        actions.addWidget(stop)
        clear = QPushButton('清空')
        clear.clicked.connect(self.clear_chat)
        actions.addWidget(clear)
        layout.addLayout(actions)
        self.retry_button = QPushButton('重试上一条失败的提问')
        self.retry_button.setEnabled(False)
        self.retry_button.clicked.connect(self.retry)
        layout.addWidget(self.retry_button)
        self.status = QLabel('就绪 · 录音需点击开始，再点击结束；最长 30 秒。')
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.PlainText)
        layout.addWidget(self.status)
        self.record_timer = QTimer(self)
        self.record_timer.setSingleShot(True)
        self.record_timer.timeout.connect(self.finish_recording)
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self.play_next)
        self.play_timer.start(50)
        threading.Thread(target=self.synthesize_loop, daemon=True).start()

    def append(self, text):
        cursor = self.transcript.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(text)
        self.transcript.setTextCursor(cursor)
        self.transcript.ensureCursorVisible()

    def save(self):
        for key, value in [('ollama', self.ollama.text()), ('speech', self.backend.text()),
                           ('model', self.model.currentText()), ('speak', self.speak.isChecked())]:
            self.settings.setValue('chat/' + key, value)
        self.settings.sync()

    def refresh(self):
        ollama, backend = self.ollama.text(), self.backend.text()
        self.refresh_button.setEnabled(False)
        self.services.setText('正在检查本地服务…')
        def run():
            result = {}
            try:
                result['models'] = [item['name'] for item in get_json(ollama, '/api/tags')['models']]
            except Exception as error:
                result['ollama_error'] = error_text(error)
            try:
                result['speech'] = get_json(backend, '/health')
            except Exception as error:
                result['speech_error'] = error_text(error)
            self.worker_event.emit(-1, 'services', result)
        threading.Thread(target=run, daemon=True).start()

    def interrupt(self):
        self.cancelled.set()
        self.turn += 1
        if self.generating:
            self.append('\n（已打断）\n')
        self.generating = False
        self.recognizing = False
        self.cancel_speech()
        if self.recording:
            self.microphone.stop()
            self.recording = False
            self.record_timer.stop()
            self.record_button.setText('开始录音')
        self.last_error = ''
        self.status.setText('已停止，可以继续说话。')

    def cancel_speech(self):
        self.speech_cancelled.set()
        self.waiting = 0
        self.voice.stop()
        self.audio_queue.clear()
        self.current_audio = None
        for path in Path(self.temp.name).glob('*.wav'):
            self.remove_clip(path)

    def speech_changed(self, enabled):
        self.save()
        if not enabled:
            self.cancel_speech()

    def clear_chat(self):
        self.interrupt()
        self.history.clear()
        self.transcript.clear()
        self.last_request = ''
        self.retry_button.setEnabled(False)

    def retry(self):
        if self.retry_button.isEnabled() and self.last_request:
            self.input.setText(self.last_request)
            self.send()

    def send(self):
        text = self.input.text().strip()
        if not text:
            return
        speak_enabled = self.speak.isChecked() and not self.settings.value('muted', False, type=bool)
        try:
            base = local_url(self.ollama.text())
            backend = local_url(self.backend.text()) if speak_enabled else ''
            model = self.model.currentText().strip()
            if not model:
                raise ValueError('请先检查连接并选择已安装的 Ollama 模型。')
        except Exception as error:
            self.status.setText(str(error))
            return
        self.interrupt()
        self.cancelled = cancelled = threading.Event()
        self.speech_cancelled = speech_cancelled = threading.Event()
        turn = self.turn
        self.generating = True
        self.last_request = text
        self.retry_button.setEnabled(False)
        self.save()
        self.input.clear()
        self.append('\n你：' + text + '\n瑠璃乃：')
        self.status.setText('Ollama 正在回复…')
        messages = [{'role': 'system', 'content': SYSTEM_PROMPT}, *self.history[-12:], {'role': 'user', 'content': text}]
        def run():
            total = ''
            sentences = Sentences()
            def enqueue(parts):
                if speak_enabled and not cancelled.is_set() and not speech_cancelled.is_set():
                    for sentence in parts:
                        self.worker_event.emit(turn, 'queued', (speech_cancelled, None))
                        self.tts_jobs.put((turn, cancelled, speech_cancelled, backend, sentence))
            try:
                for chunk in stream_reply(base, model, messages, cancelled):
                    if cancelled.is_set():
                        return
                    total += chunk
                    self.worker_event.emit(turn, 'chunk', chunk)
                    enqueue(sentences.feed(chunk))
                if not cancelled.is_set():
                    if not total.strip():
                        raise ValueError('Ollama 没有返回可显示的回复。')
                    enqueue(sentences.feed('', final=True))
                    self.worker_event.emit(turn, 'done', (text, total))
            except Exception as error:
                if not cancelled.is_set():
                    self.worker_event.emit(turn, 'chat_error', '聊天失败：' + error_text(error))
        threading.Thread(target=run, daemon=True).start()

    def synthesize_loop(self):
        while True:
            job = self.tts_jobs.get()
            if job is None:
                return
            turn, cancelled, speech_cancelled, backend, sentence = job
            if cancelled.is_set() or speech_cancelled.is_set():
                continue
            try:
                wav = speech(backend, sentence)
                if not cancelled.is_set() and not speech_cancelled.is_set():
                    self.worker_event.emit(turn, 'audio', (speech_cancelled, wav))
            except Exception as error:
                if not cancelled.is_set() and not speech_cancelled.is_set():
                    self.worker_event.emit(turn, 'tts_error', (speech_cancelled, '语音合成失败（文字仍可使用）：' + error_text(error)))

    def record(self):
        if self.recording:
            self.finish_recording()
            return
        self.interrupt()
        self.cancelled = threading.Event()
        try:
            local_url(self.backend.text())
            self.microphone.start()
            self.recording = True
            self.record_button.setText('结束并发送')
            self.status.setText('正在录音，点击“结束并发送”完成；30 秒后自动结束。')
            self.record_timer.start(30000)
        except Exception as error:
            self.status.setText(str(error))

    def finish_recording(self):
        if not self.recording:
            return
        self.record_timer.stop()
        wav = self.microphone.stop()
        self.recording = False
        self.record_button.setText('开始录音')
        if not wav:
            self.status.setText('没有录到声音，请检查麦克风。')
            return
        self.status.setText('正在本地识别…首次使用需加载 Whisper。')
        self.recognizing = True
        turn, cancelled = self.turn, self.cancelled
        backend, language = self.backend.text(), self.language.currentData()
        def run():
            try:
                text = transcribe(backend, wav, language)
                if not cancelled.is_set():
                    self.worker_event.emit(turn, 'recognized', text)
            except Exception as error:
                if not cancelled.is_set():
                    self.worker_event.emit(turn, 'error', '语音识别失败：' + error_text(error))
        threading.Thread(target=run, daemon=True).start()

    def handle_event(self, turn, kind, payload):
        if kind == 'services':
            self.refresh_button.setEnabled(True)
            previous = self.model.currentText()
            if 'models' in payload:
                self.model.clear()
                self.model.addItems(payload['models'])
                if previous in payload['models']:
                    self.model.setCurrentText(previous)
                ollama = 'Ollama 已连接' if payload['models'] else 'Ollama 已连接，但还没有模型；请先 ollama pull qwen3:1.7b'
            else:
                ollama = 'Ollama 未连接：' + payload['ollama_error']
            ready = payload.get('speech', {})
            state = ready.get('tts_state', 'ready' if ready.get('tts_loaded') else 'not_loaded')
            state_text = {'not_loaded': '尚未加载音色', 'loading': '正在加载或预热',
                          'ready': '音色就绪', 'synthesizing': '正在合成', 'error': '音色加载/合成失败'}.get(state, state)
            backend = ('语音服务已连接：' + state_text + ' · ' + ready.get('device', '')) if ready.get('service') == 'rurino-speech' else '语音服务未连接，请启动 Start-Voice-Service.cmd'
            if ready.get('tts_error'):
                backend += '\n' + ready['tts_error']
            self.services.setText(ollama + '\n' + backend)
            self.save()
            return
        if turn != self.turn:
            return
        if kind in ('queued', 'audio', 'tts_error'):
            speech_cancelled, payload = payload
            if speech_cancelled is not self.speech_cancelled or speech_cancelled.is_set():
                return
        if kind == 'chunk':
            self.append(payload)
        elif kind == 'queued':
            self.waiting += 1
        elif kind == 'done':
            self.generating = False
            question, answer = payload
            self.history.extend([{'role': 'user', 'content': question}, {'role': 'assistant', 'content': answer}])
            self.history = self.history[-12:]
        elif kind in ('error', 'chat_error'):
            self.generating = False
            self.recognizing = False
            self.last_error = payload
            self.status.setText(payload)
            if kind == 'chat_error':
                self.retry_button.setEnabled(True)
        elif kind == 'tts_error':
            self.waiting = max(0, self.waiting - 1)
            self.last_error = payload
            self.status.setText(payload)
        elif kind == 'audio':
            self.waiting = max(0, self.waiting - 1)
            if self.speak.isChecked() and not self.controller.settings.value('muted', False, type=bool):
                self.audio_queue.append(payload)
        elif kind == 'recognized':
            self.recognizing = False
            self.input.setText(payload)
            self.send()

    def play_next(self):
        if self.recording or self.recognizing:
            return
        if self.voice.playing():
            if self.current_audio and not self.last_error:
                self.status.setText('瑠璃乃正在说话…可以随时点击“打断”。')
            return
        if self.current_audio:
            self.voice.stop()
            self.remove_clip(self.current_audio)
            self.current_audio = None
        if self.audio_queue:
            if self.controller.settings.value('muted', False, type=bool) or not self.speak.isChecked():
                self.audio_queue.clear()
                return
            wav = self.audio_queue.popleft()
            path = Path(self.temp.name) / f'{self.turn}-{uuid.uuid4().hex}.wav'
            try:
                path.write_bytes(wav)
                self.voice.load(path)
                self.voice.play()
                self.current_audio = path
            except Exception as error:
                self.last_error = '播放失败：' + str(error)
                self.status.setText(self.last_error)
            return
        if self.last_error:
            return
        if self.waiting:
            self.status.setText('正在合成你的音色…首次加载和 CPU 推理可能较慢。')
        elif self.generating:
            self.status.setText('Ollama 正在回复…')
        else:
            self.status.setText('就绪 · 可以继续输入或录音。')

    def closeEvent(self, event):
        self.interrupt()
        self.save()
        event.accept()

    @staticmethod
    def remove_clip(path):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            # Windows audio drivers can release a completed WAV handle slightly late.
            # A later interruption/shutdown retries temporary-file cleanup.
            pass

    def shutdown(self):
        self.interrupt()
        self.tts_jobs.put(None)
        self.temp.cleanup()
