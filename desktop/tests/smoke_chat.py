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


def wait_for(predicate, seconds=4, detail=None):
    end = time.monotonic() + seconds
    while not predicate() and time.monotonic() < end:
        QTest.qWait(20)
    assert predicate(), 'Condition timed out' + (f' [{detail()}]' if detail else '')


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
    chat.backend.setText('not a service URL')
    chat.input.setText('没有语音服务也能聊')
    chat.send()
    wait_for(lambda: len(chat.history) == 8)

    chat.backend.setText(base)
    chat.speak.setChecked(True)
    chat.input.setText('slow')
    chat.send()
    wait_for(lambda: '今日は' in chat.transcript.toPlainText().split('瑠璃乃：')[-1])
    old_speech = chat.speech_cancelled
    chat.speak.setChecked(False)
    assert chat.generating, 'Turning off narration must preserve the text stream'
    chat.speak.setChecked(True)
    chat.handle_event(chat.turn, 'audio', (old_speech, wav_bytes()))
    wait_for(lambda: len(chat.history) == 10)
    assert len(played) == 4 and not chat.audio_queue

    chat.speak.setChecked(False)
    chat.input.setText('retry-once')
    chat.send()
    wait_for(lambda: chat.retry_button.isEnabled())
    assert len(chat.history) == 10
    chat.retry()
    wait_for(lambda: len(chat.history) == 12)
    assert chat.history[-2]['content'] == 'retry-once' and not chat.retry_button.isEnabled()

    # The Chinese subtitle is a second local request shown as text, never spoken.
    chat.speak.setChecked(False)
    chat.subtitle.setChecked(True)
    def translations():
        return len([item for item in requests if item[0] == 'chat' and item[1].get('stream') is False])
    before = translations()
    transcript_before = chat.transcript.toPlainText()
    chat.input.setText('字幕测试')
    chat.send()
    wait_for(lambda: translations() == before + 1)
    wait_for(lambda: chat.history[-2]['content'] == '字幕测试', seconds=8)
    # Only look at text added by this turn: earlier turns show the same subtitle.
    def new_text():
        return chat.transcript.toPlainText()[len(transcript_before):]
    wait_for(lambda: '〔中文〕' in new_text(), seconds=8, detail=lambda: f'added={new_text()!r}')
    assert '今天也很有精神哦' in new_text()

    # Saved memory must reach the model as part of the system prompt.
    chat.memory.update('小明', ['喜欢猫'])
    chat.input.setText('记忆测试')
    chat.send()
    wait_for(lambda: chat.history[-2]['content'] == '记忆测试', seconds=8)
    last = [item for item in requests if item[0] == 'chat' and item[1].get('stream') is True][-1][1]
    assert '小明' in last['messages'][0]['content'], '称呼必须进入系统提示'
    assert '- 喜欢猫' in last['messages'][0]['content'], '备注必须进入系统提示'
    assert last['messages'][0]['role'] == 'system'

    # Auto-send: speech followed by a pause ends the recording without a click.
    chat.microphone = Mock()
    levels = iter([.2] * 20 + [.0] * 80)
    chat.microphone.level.side_effect = lambda: next(levels, 0.0)
    chat.microphone.stop.return_value = wav_bytes()
    chat.auto_send.setChecked(True)
    chat.pause.setCurrentIndex(1)
    chat.record()
    assert chat.recording and chat.detector is not None
    def recording_detail():
        detector = chat.detector
        heard = f'{detector.heard:.2f}' if detector else 'n/a'
        quiet = f'{detector.quiet:.2f}' if detector else 'n/a'
        return f'recording={chat.recording} heard={heard} quiet={quiet} status={chat.status.text()!r}'
    wait_for(lambda: not chat.recording, seconds=12, detail=recording_detail)
    wait_for(lambda: chat.history[-2]['content'] == '今天好吗？', seconds=12,
             detail=lambda: f'history={chat.history[-2:]} status={chat.status.text()!r}')
    assert chat.history[-1]['role'] == 'assistant', '自动发送必须走完识别与提问'

    output = ROOT/'test-output'
    output.mkdir(exist_ok=True)
    chat.grab().save(str(output/'chat-protocol-test.png'))
    chat.clear_chat()
    assert not chat.history and not chat.transcript.toPlainText()
    chat.close()
    setup.shutdown()
    setup.close()
    QTest.qWait(100)
print('PASS: local discovery, streaming, speech clips, history, cancellation, ASR pipeline, auto-send on pause, Chinese subtitle, memory in system prompt, text-only without speech config, narration-only cancellation, stale-audio rejection, failure retry, cleanup')
