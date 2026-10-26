"""Simplified desktop pet drawn from the handoff layer PNGs.

Used when no Cubism model exists. It blinks, breathes, follows the cursor with
its irises and moves its mouth while speech plays -- but it is not Live2D: no
mesh deformation, no head perspective. The setup window says so, and picking a
`.model3.json` replaces this window with the real renderer.
"""
import json
import math
from pathlib import Path
import random
import time

from PyQt5.QtCore import QPoint, Qt, QTimer
from PyQt5.QtGui import QCursor, QIcon, QImage, QPainter
from PyQt5.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

from sprites import Sprites

ROOT = Path(__file__).resolve().parent
LAYERS = ROOT / 'assets' / 'layers'
SCALE = 0.34


def to_qimage(image):
    """Convert a PIL RGBA image into a QImage that owns its pixels."""
    data = image.tobytes('raw', 'RGBA')
    return QImage(data, image.width, image.height, QImage.Format_RGBA8888).copy()


def load_sprites():
    return Sprites(LAYERS, scale=SCALE).build()


class SpritePet(QWidget):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.settings = controller.settings
        self.voice = controller.voice
        self.on_top = self.settings.value('on_top', True, type=bool)
        self.muted = self.settings.value('muted', False, type=bool)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool |
                            (Qt.WindowStaysOnTopHint if self.on_top else Qt.Widget))
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle('瑠璃乃 · 简化模式')
        icon = ROOT / 'assets' / 'rurino.ico'
        if icon.is_file():
            self.setWindowIcon(QIcon(str(icon)))
        self.setCursor(Qt.OpenHandCursor)

        self.sprites = load_sprites()
        self.resize(*self.sprites.size)
        self.image = to_qimage(self.sprites.frame())

        self.press_origin = None
        self.window_origin = QPoint()
        self.dragging = False
        self.blink_at = time.monotonic() + random.uniform(1.5, 4.0)
        self.blink_started = None
        self.mouth = 0.0
        self.started = time.monotonic()

        self.tray = QSystemTrayIcon(self.windowIcon(), self)
        self.tray.setToolTip('瑠璃乃 · 双击显示，右键退出')
        self.tray.activated.connect(self.tray_activated)
        self.refresh_menu()
        if QSystemTrayIcon.isSystemTrayAvailable():
            self.tray.show()

        screen = QApplication.primaryScreen().availableGeometry()
        saved = self.settings.value('position', QPoint(screen.right() - self.width(),
                                                       screen.bottom() - self.height()), type=QPoint)
        self.move(saved)
        self.keep_on_screen()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)

    # --- animation -------------------------------------------------------
    def state(self, now):
        elapsed = now - self.started
        breath = (math.sin(elapsed * math.tau / 4.0) + 1) / 2
        sway = math.sin(elapsed * math.tau / 7.0) * .45

        eye_open = 1.0
        if self.blink_started is not None:
            progress = (now - self.blink_started) / .13
            if progress >= 1:
                self.blink_started = None
                self.blink_at = now + random.uniform(2.5, 7.0)
            else:
                eye_open = abs(progress * 2 - 1)      # 1 -> 0 -> 1
        elif now >= self.blink_at:
            self.blink_started = now
            eye_open = 0.0

        speaking = self.voice.playing() and not self.muted
        target = self.voice.mouth() if speaking else 0.0
        self.mouth += (target - self.mouth) * .5        # smooth, no jitter

        return dict(eye_open=eye_open, mouth=min(1.0, self.mouth * 1.6),
                    sway=sway, breath=breath)

    def tick(self):
        if not self.isVisible():
            return
        self.image = to_qimage(self.sprites.frame(**self.state(time.monotonic())))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.drawImage(0, 0, self.image)

    # --- interaction -----------------------------------------------------
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

    def make_menu(self):
        menu = QMenu(self)
        menu.addAction('和瑠璃乃聊天…', self.controller.open_chat)
        menu.addAction('打招呼', self.greet)
        mute = menu.addAction('静音', self.toggle_mute)
        mute.setCheckable(True)
        mute.setChecked(self.muted)
        top = menu.addAction('始终置顶', self.toggle_top)
        top.setCheckable(True)
        top.setChecked(self.on_top)
        if self.tray.isVisible():
            menu.addAction('隐藏 / 显示', self.toggle_visible)
        menu.addSeparator()
        menu.addAction('改用 Cubism 模型…', lambda: self.controller.return_to_setup(
            '选择 Cubism 导出的 .model3.json；分层简化模式会关闭。'))
        menu.addAction('退出', self.close)
        return menu

    def refresh_menu(self):
        old = self.tray.contextMenu()
        self.tray.setContextMenu(self.make_menu())
        if old:
            old.deleteLater()

    def greet(self):
        if self.muted or self.voice.playing():
            return
        self.controller.stop_conversation()
        self.voice.load(ROOT / 'assets' / 'greeting.wav')
        self.voice.play()

    def toggle_mute(self):
        self.muted = not self.muted
        if self.muted:
            self.controller.stop_conversation()
            self.voice.stop()
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

    def keep_on_screen(self):
        screen = QApplication.screenAt(self.geometry().center()) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        self.move(max(area.left(), min(self.x(), area.right() - self.width() + 1)),
                  max(area.top(), min(self.y(), area.bottom() - self.height() + 1)))

    def save(self):
        for key in ('on_top', 'muted'):
            self.settings.setValue(key, getattr(self, key))
        self.settings.setValue('position', self.pos())
        self.settings.sync()

    def shutdown(self):
        self.timer.stop()
        self.voice.stop()
        self.tray.hide()
        self.save()
        self.hide()

    def closeEvent(self, event):
        self.shutdown()
        QApplication.instance().quit()
        event.accept()
