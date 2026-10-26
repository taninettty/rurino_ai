"""Run on a disposable display with a real exported .model3.json argument."""
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PyQt5.QtCore import QSettings, QPoint, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication
from PIL import Image
import app as module

module.configure_graphics()
application = QApplication([])
application.setQuitOnLastWindowClosed(False)
with tempfile.TemporaryDirectory() as directory:
    settings = QSettings(str(Path(directory) / 'settings.ini'), QSettings.IniFormat)
    setup = module.Setup(settings)
    setup.show()
    QTest.qWait(150)
    output = ROOT / 'test-output'
    output.mkdir(exist_ok=True)
    setup.grab().save(str(output / 'setup.png'))
    assert setup.pet is None, 'No exported model means no desktop pet'
    assert not setup.load_model(ROOT / 'assets/approved.png')
    assert setup.pet is None and setup.isVisible()
    assert setup.load_model(sys.argv[1])
    QTest.qWait(1500)
    pet = setup.pet
    assert pet and pet.ready, setup.status.text()
    assert not setup.isVisible()
    assert pet.view.model.GetParamCount() > 0
    image = pet.view.grabFramebuffer()
    image.save(str(output / 'test-model.png'))
    rgba = Image.open(output / 'test-model.png').convert('RGBA')
    assert rgba.getchannel('A').getextrema() == (0, 255), 'Real transparent model pixels expected'
    assert len(rgba.getcolors(rgba.width * rgba.height)) > 50, 'Rendered model must contain image detail'
    assert settings.value('model_path') == str(Path(sys.argv[1]).resolve())

    # Avoid audible output while verifying mouth animation with the real envelope.
    pet.voice.started = time.monotonic() - .7
    pet.view.update()
    QTest.qWait(100)
    assert pet.voice.playing() and pet.view.was_speaking
    pet.toggle_mute()
    pet.view.update()
    QTest.qWait(80)
    assert not pet.voice.playing() and pet.voice.mouth() == 0
    assert pet.view.model.GetParamValueById('ParamMouthOpenY') == 0
    old_top = pet.on_top
    pet.toggle_top()
    QTest.qWait(100)
    assert pet.on_top != old_top and pet.ready and not pet.view.broken
    pet.set_size(500)
    QTest.qWait(80)
    assert pet.width() == 500 and settings.value('size', type=int) == 500
    assert pet.view.width() == pet.width()
    pet.toggle_follow()
    assert not pet.follow and not settings.value('follow', type=bool)
    point = QPoint(100, 100)
    before = pet.pos()
    QTest.mousePress(pet, Qt.LeftButton, pos=point)
    QTest.mouseMove(pet, point + QPoint(-60, -40), delay=30)
    QTest.qWait(80)
    QTest.mouseRelease(pet, Qt.LeftButton, pos=point + QPoint(-60, -40))
    assert pet.pos() != before and not pet.voice.playing(), (before, pet.pos(), pet.dragging)
    setup.return_to_setup()
    QTest.qWait(100)
    assert setup.pet is None and setup.isVisible()
    assert setup.load_model(sys.argv[1])
    QTest.qWait(900)
    assert setup.pet and setup.pet.ready, 'Reload must retain a working GL context'
    setup.return_to_setup()
    QTest.qWait(100)
    setup.close()
    QTest.qWait(50)
if module.LIVE2D:
    module.LIVE2D.dispose()
print('PASS: setup, invalid-model recovery, real transparent rendering, audio envelope, mute, topmost, sizing, dragging, settings, reload, cleanup')
