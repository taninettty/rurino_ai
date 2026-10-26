"""Qt orchestration test with local protocol doubles and silent playback."""
from pathlib import Path
import sys
import tempfile
import time
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PyQt5.QtCore import QSettings
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication
from protocol_fixture import protocol_server, wav_bytes
import app as module

module.configure_graphics()
application = QApplication([])
application.setQuitOnLastWindowClosed(False)


def wait_for(predicate, seconds=4):
    end = time.monotonic() + seconds
    while not predicate() and time.monotonic() < end:
        QTest.qWait(20)
    assert predicate(), 'Condition timed out'


with tempfile.TemporaryDirectory() as directory, protocol_server() as (base, requests):
    setup = module.Setup(QSettings(str(Path(directory)/'settings.ini'), QSettings.IniFormat))
    setup.show()
    setup.open_chat()
    chat = setup.chat_window
    chat.ollama.setText(base)
    chat.backend.setText(base)
    played = []
    def silent_play():
        played.append(setup.voice.path)
        setup.voice.started = time.monotonic()
        setup.voice.duration = .05
    setup.voice.play = silent_play
    chat.refresh()
    wait_for(lambda: chat.refresh_button.isEnabled())
    assert chat.model.currentText() == 'test-local'
    chat.input.setText('你好')
    chat.send()
    wait_for(lambda: len(chat.history) == 2 and len(played) == 2)
    assert len(set(played)) == 2, 'Sentences must use different WAV URLs (Qt caches sources)'
    assert '今日は元気だよ。' in chat.transcript.toPlainText()
    assert not setup.pet, 'Conversation must work before Cubism rigging'
    wait_for(lambda: not chat.voice.playing() and chat.current_audio is None)

    chat.input.setText('slow')
    chat.send()
    wait_for(lambda: '今日は' in chat.transcript.toPlainText().split('瑠璃乃：')[-1])
    old_turn = chat.turn
    chat.interrupt()
    chat.handle_event(old_turn, 'audio', wav_bytes())
    QTest.qWait(1100)
    assert len(chat.history) == 2 and len(played) == 2 and not chat.audio_queue

    # Exercise the record -> recognize -> auto-send path without real microphone hardware.
    chat.microphone = Mock()
    chat.microphone.stop.return_value = wav_bytes()
    chat.record()
    assert chat.recording
    chat.finish_recording()
    wait_for(lambda: len(chat.history) == 4 and len(played) == 4)
    assert chat.history[-2]['content'] == '今天好吗？'

    # Turning speech off cancels queued playback; text-only mode must not request TTS.
    chat.speak.setChecked(False)
    count = len([item for item in requests if item[0] == 'tts'])
    chat.input.setText('文字测试')
    chat.send()
    wait_for(lambda: len(chat.history) == 6)
    assert len([item for item in requests if item[0] == 'tts']) == count
    output = ROOT/'test-output'
    output.mkdir(exist_ok=True)
    chat.grab().save(str(output/'chat-protocol-test.png'))
    chat.clear_chat()
    assert not chat.history and not chat.transcript.toPlainText()
    chat.close()
    setup.shutdown()
    setup.close()
    QTest.qWait(100)
print('PASS: local discovery, streamed chat, distinct speech clips, history, cancellation, stale-output rejection, record-to-send pipeline, text-only mode, cleanup')
