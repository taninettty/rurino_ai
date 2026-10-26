"""Live2D-only desktop host. Approved artwork is shown only in the setup window."""
import logging
import os
from pathlib import Path
import sys
import time

from PyQt5.QtCore import Qt, QTimer, QPoint, QSettings, pyqtSignal
from PyQt5.QtGui import QCursor, QIcon, QPixmap, QSurfaceFormat
from PyQt5.QtWidgets import (QApplication, QWidget, QOpenGLWidget, QVBoxLayout,
                            QLabel, QPushButton, QFileDialog, QMenu, QSystemTrayIcon)

from model_support import validate_model
from voice import Voice

ROOT = Path(__file__).resolve().parent
LIVE2D = None


class ModelView(QOpenGLWidget):
    loaded = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, pet, path):
        super().__init__(pet)
        self.pet, self.path = pet, path
        self.model = None
        self.broken = False
        self.groups = {}
        self.params = set()
        self.was_speaking = False
        self.previous = time.monotonic()
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_AlwaysStackOnTop)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAutoFillBackground(False)

    def initializeGL(self):
        global LIVE2D
        try:
            if LIVE2D is None:
                import live2d
                live2d.init()
                LIVE2D = live2d
            LIVE2D.glInit()
            self.model = LIVE2D.Model()
            self.model.LoadModelJson(str(self.path))
            self.model.Resize(self.width(), self.height())
            if self.model.GetParamCount() == 0:
                raise ValueError('模型没有可用参数。请检查 Cubism 导出结果。')
            self.groups = self.model.GetMotionGroups()
            self.params = set(self.model.GetParamIds())
            self.model.SetAutoBlink(True)
            self.model.SetAutoBreath(True)
            QTimer.singleShot(0, self.loaded.emit)
        except Exception as error:
            self.report_failure(error)

    def report_failure(self, error):
        self.broken = True
        logging.exception('Live2D failure')
        QTimer.singleShot(0, lambda message=str(error): self.failed.emit(message))

    def resizeGL(self, width, height):
        if self.model and not self.broken:
            self.model.Resize(width, height)

    def paintGL(self):
        if self.broken or not self.model:
            return
        try:
            LIVE2D.clearBuffer(0, 0, 0, 0)
            now = time.monotonic()
            mouse = self.mapFromGlobal(QCursor.pos())
            if self.pet.follow:
                half_w, half_h = max(1, self.width() / 2), max(1, self.height() / 2)
                dx = max(-.4, min(.4, (mouse.x() - half_w) / half_w))
                dy = max(-.3, min(.3, (mouse.y() - half_h) / half_h))
                self.model.Drag(half_w * (1 + dx), half_h * (1 + dy))
            else:
                self.model.Drag(self.width() / 2, self.height() / 2)
            self.model.Update(min(.1, now - self.previous))
            self.previous = now
            speaking = self.pet.voice.playing()
            if 'ParamMouthOpenY' in self.params and (speaking or self.was_speaking):
                self.model.SetParamById('ParamMouthOpenY', self.pet.voice.mouth() if speaking else 0)
            self.was_speaking = speaking
            # Only use exported idle motions; do not invent a waving animation.
            idle = next((group for group in self.groups if group.lower() == 'idle'), None)
            if idle and self.model.IsMotionFinished():
                self.model.StartRandomMotion(idle, 1)
            self.model.Draw()
        except Exception as error:
            self.report_failure(error)

    def release(self):
        self.broken = True
        if self.context() and self.model:
            self.makeCurrent()
            self.model.DestroyRenderer()
            self.model = None
            self.doneCurrent()


class Pet(QWidget):
    def __init__(self, controller, path, data):
        super().__init__()
        self.controller, self.path, self.data = controller, path, data
        self.settings = controller.settings
        self.ready = False
        self.press_origin = None
        self.dragging = False
        self.muted = self.settings.value('muted', False, type=bool)
        self.on_top = self.settings.value('on_top', True, type=bool)
        self.follow = self.settings.value('follow', True, type=bool)
        self.size = max(240, min(600, self.settings.value('size', 340, type=int)))
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool |
                            (Qt.WindowStaysOnTopHint if self.on_top else Qt.Widget))
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle('瑠璃乃 · Live2D')
        self.setWindowIcon(QIcon(str(ROOT / 'assets/approved.png')))
        self.setCursor(Qt.OpenHandCursor)
        self.setMouseTracking(True)
        self.voice = controller.voice
        self.view = ModelView(self, path)
        self.view.loaded.connect(self.model_ready)
        self.view.failed.connect(self.model_failed)
        self.resize(self.size, round(self.size * 4 / 3))
        self.view.setGeometry(self.rect())
        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip('瑠璃乃 · 双击显示，右键退出')
        self.tray.activated.connect(self.tray_activated)
        self.refresh_menu()
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()
            self.refresh_menu()
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(self.settings.value('position', QPoint(screen.right()-self.width(), screen.bottom()-self.height()), type=QPoint))
        self.keep_on_screen()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)

    def model_ready(self):
        if self.view.broken:
            return
        self.ready = True
        self.settings.setValue('model_path', str(self.path))
        self.settings.sync()
        self.controller.hide()

    def model_failed(self, message):
        self.controller.return_to_setup('模型加载失败：' + message)

    def tick(self):
        if self.isVisible():
            self.view.update()

    def greet(self):
        if self.ready and not self.muted and not self.voice.playing():
            self.controller.stop_conversation()
            self.voice.load(ROOT / 'assets/greeting.wav')
            self.voice.play()

    def resizeEvent(self, event):
        self.view.setGeometry(self.rect())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.press_origin = event.globalPos()
            self.window_origin = self.pos()
            self.dragging = False
            self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self.press_origin is not None:
            delta = event.globalPos() - self.press_origin
            self.dragging |= delta.manhattanLength() > QApplication.startDragDistance()
            if self.dragging:
                self.move(self.window_origin + delta)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.press_origin is not None:
            if not self.dragging:
                self.controller.open_chat()
            self.press_origin = None
            self.setCursor(Qt.OpenHandCursor)
            self.keep_on_screen()
            self.save()

    def contextMenuEvent(self, event):
        menu = self.make_menu()
        menu.exec_(event.globalPos())
        menu.deleteLater()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.controller.stop_conversation()
            self.voice.stop()
        elif event.key() == Qt.Key_Space:
            self.greet()
        elif event.key() == Qt.Key_M:
            self.toggle_mute()

    def wheelEvent(self, event):
        self.set_size(self.size + (20 if event.angleDelta().y() > 0 else -20))

    def set_size(self, size):
        bottom = self.geometry().bottomRight()
        self.size = max(240, min(600, size))
        self.resize(self.size, round(self.size * 4 / 3))
        self.move(bottom - QPoint(self.width()-1, self.height()-1))
        self.keep_on_screen()
        self.save()

    def keep_on_screen(self):
        screen = QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        self.move(max(area.left(), min(self.x(), area.right()-self.width()+1)),
                  max(area.top(), min(self.y(), area.bottom()-self.height()+1)))

    def make_menu(self):
        menu = QMenu(self)
        menu.addAction('和瑠璃乃聊天…', self.controller.open_chat)
        menu.addAction('打招呼', self.greet)
        for title, state, callback in [('静音', self.muted, self.toggle_mute),
                                       ('始终置顶', self.on_top, self.toggle_top),
                                       ('目光跟随', self.follow, self.toggle_follow)]:
            action = menu.addAction(title, callback)
            action.setCheckable(True)
            action.setChecked(state)
        menu.addAction('恢复默认大小', lambda: self.set_size(340))
        if self.tray.isVisible():
            menu.addAction('隐藏 / 显示', self.toggle_visible)
        menu.addSeparator()
        menu.addAction('更换模型…', lambda: self.controller.return_to_setup())
        menu.addAction('退出', self.close)
        return menu

    def refresh_menu(self):
        old = self.tray.contextMenu()
        self.tray.setContextMenu(self.make_menu())
        if old:
            old.deleteLater()

    def toggle_mute(self):
        self.muted = not self.muted
        if self.muted:
            if self.controller.chat_window:
                self.controller.chat_window.cancel_speech()
            self.voice.stop()
        self.save()
        self.refresh_menu()

    def toggle_follow(self):
        self.follow = not self.follow
        self.save()
        self.refresh_menu()

    def toggle_top(self):
        self.on_top = not self.on_top
        self.setWindowFlag(Qt.WindowStaysOnTopHint, self.on_top)
        self.show()
        self.save()
        self.refresh_menu()

    def toggle_visible(self):
        self.voice.stop()
        self.setVisible(not self.isVisible())

    def tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()
            self.raise_()

    def save(self):
        for key in ('muted', 'on_top', 'follow', 'size'):
            self.settings.setValue(key, getattr(self, key))
        self.settings.setValue('position', self.pos())
        self.settings.sync()

    def shutdown(self):
        self.timer.stop()
        self.voice.stop()
        self.view.release()
        self.tray.hide()
        self.save()
        self.hide()

    def closeEvent(self, event):
        self.shutdown()
        QApplication.instance().quit()
        event.accept()


class Setup(QWidget):
    def __init__(self, settings=None):
        super().__init__()
        self.settings = settings or QSettings('RurinoLive2D', 'Desktop')
        self.pet = None
        self.chat_window = None
        self.setWindowTitle('瑠璃乃 · Live2D 模型接入')
        self.setMinimumWidth(400)
        self.setStyleSheet('QWidget {background:#fff8fb;color:#513c49;font-size:14px;} '
                           'QPushButton {background:#f4d8e5;padding:12px;border:0;border-radius:8px;} '
                           'QLabel {padding:4px;}')
        layout = QVBoxLayout(self)
        title = QLabel('瑠璃乃 · 已确认形象')
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        picture = QLabel()
        picture.setPixmap(QPixmap(str(ROOT / 'assets/approved.png')).scaled(240, 320, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        picture.setAlignment(Qt.AlignCenter)
        layout.addWidget(picture)
        self.status = QLabel('等待 Cubism 导出的模型。\n请选择完整模型文件夹中的 .model3.json。')
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.PlainText)
        layout.addWidget(self.status)
        choose = QPushButton('选择 Live2D 模型文件…')
        choose.clicked.connect(self.choose_model)
        layout.addWidget(choose)
        self.simplified_button = QPushButton('先用分层立绘启动（简化模式）')
        self.simplified_button.clicked.connect(self.start_simplified)
        layout.addWidget(self.simplified_button)
        self.voice = Voice(ROOT / 'assets/greeting.wav', self)
        self.preview_button = QPushButton('试听现有音色')
        self.preview_button.clicked.connect(self.preview_voice)
        layout.addWidget(self.preview_button)
        chat_button = QPushButton('和瑠璃乃聊天 · 本地 Ollama')
        chat_button.clicked.connect(self.open_chat)
        layout.addWidget(chat_button)
        self.audio_timer = QTimer(self)
        self.audio_timer.timeout.connect(self.update_audio_button)
        self.audio_timer.start(100)
        help_text = QLabel('导入后：拖动移动 · 滚轮缩放 · 点击聊天\n右键设置与退出 · M 静音 · Esc 打断对话')
        help_text.setAlignment(Qt.AlignCenter)
        layout.addWidget(help_text)

    def preview_voice(self):
        if self.voice.playing():
            self.stop_conversation()
            self.voice.stop()
        else:
            self.stop_conversation()
            self.voice.load(ROOT / 'assets/greeting.wav')
            self.voice.play()
        self.update_audio_button()

    def open_chat(self):
        if self.chat_window is None:
            from chat import ChatWindow
            self.chat_window = ChatWindow(self)
        self.chat_window.show()
        self.chat_window.raise_()
        self.chat_window.activateWindow()

    def start_simplified(self):
        """Show the layered stand-in pet when no Cubism model is available."""
        if not (ROOT / 'assets' / 'layers' / 'layers.json').is_file():
            self.status.setText('缺少分层素材，请重新获取程序包。')
            return False
        try:
            from sprite_pet import SpritePet
            if self.pet:
                self.pet.shutdown()
                self.pet.deleteLater()
            self.pet = SpritePet(self)
            self.pet.show()
            self.hide()
            return True
        except Exception as error:
            logging.exception('Simplified pet failed')
            self.status.setText('简化模式启动失败：' + str(error))
            self.show()
            return False

    def stop_conversation(self):
        if self.chat_window:
            self.chat_window.interrupt()

    def shutdown(self):
        if self.chat_window:
            self.chat_window.shutdown()
        self.voice.stop()

    def update_audio_button(self):
        self.preview_button.setText('停止试听' if self.voice.playing() else '试听现有音色')

    def choose_model(self):
        filename, _ = QFileDialog.getOpenFileName(self, '选择导出的模型', '', 'Live2D (*.model3.json)')
        if filename:
            self.load_model(filename)

    def load_model(self, filename):
        try:
            path, data = validate_model(filename)
            self.voice.stop()
            if self.pet:
                self.pet.shutdown()
                self.pet.deleteLater()
                self.pet = None
            self.pet = Pet(self, path, data)
            self.status.setText('正在加载模型…')
            self.pet.show()
            # Unsupported OpenGL platforms may never invoke initializeGL.
            pending = self.pet
            QTimer.singleShot(8000, lambda: self.check_loading(pending))
            return True
        except Exception as error:
            logging.exception('Model selection failed')
            self.status.setText(str(error))
            self.show()
            return False

    def check_loading(self, pending):
        if self.pet is pending and not pending.ready:
            self.return_to_setup('无法初始化图形环境，请检查显卡驱动和 OpenGL 支持。')

    def return_to_setup(self, message='请选择要使用的 Live2D 模型。'):
        if self.pet:
            self.pet.shutdown()
            self.pet.deleteLater()
            self.pet = None
        self.status.setText(message)
        self.show()
        self.raise_()

    def closeEvent(self, event):
        self.voice.stop()
        if self.pet:
            self.pet.shutdown()
        QApplication.instance().quit()
        event.accept()


def configure_graphics():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
    # Keeps the OpenGL context alive when the always-on-top flag changes.
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    fmt = QSurfaceFormat()
    fmt.setAlphaBufferSize(8)
    fmt.setVersion(2, 1)
    QSurfaceFormat.setDefaultFormat(fmt)


def main():
    log_dir = Path(os.environ.get('LOCALAPPDATA', Path.home() / '.local/share')) / 'RurinoLive2D'
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=log_dir / 'desktop.log', level=logging.INFO)
    if sys.stdout is None:
        sys.stdout = open(log_dir / 'runtime.log', 'a', encoding='utf-8')
    if sys.stderr is None:
        sys.stderr = sys.stdout
    configure_graphics()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    setup = Setup()
    app.aboutToQuit.connect(setup.shutdown)
    setup.show()
    saved = setup.settings.value('model_path', '', type=str)
    if saved:
        QTimer.singleShot(0, lambda: setup.load_model(saved))
    else:
        # No rigged model yet: open the layered stand-in instead of an empty
        # import window, so the shortcut leads to something alive.
        QTimer.singleShot(0, setup.start_simplified)
    result = app.exec_()
    if LIVE2D:
        LIVE2D.dispose()
    return result


if __name__ == '__main__':
    sys.exit(main())
