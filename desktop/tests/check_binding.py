"""Check whether the exported model actually reacts to the parameters the pet drives.

Loads the model through the real Qt/OpenGL path (the same one the desktop pet
uses), then sets each parameter to its extremes and compares the rendered
frames. Different pixels mean the keyforms are bound; identical pixels mean the
parameter exists but nothing is attached to it.
"""
from pathlib import Path
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PyQt5.QtCore import QBuffer, QIODevice, QSettings
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication
import app as module

CHECKS = [('ParamEyeLOpen', 0.0, 1.0), ('ParamEyeROpen', 0.0, 1.0),
          ('ParamMouthOpenY', 0.0, 1.0), ('ParamAngleX', -15.0, 15.0)]

model = sys.argv[1]
module.configure_graphics()
application = QApplication([])
application.setQuitOnLastWindowClosed(False)

with tempfile.TemporaryDirectory() as directory:
    setup = module.Setup(QSettings(str(Path(directory) / 'settings.ini'), QSettings.IniFormat))
    setup.show()
    assert setup.load_model(model), 'load_model refused the file'
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline and not (setup.pet and setup.pet.ready):
        QTest.qWait(50)
    pet = setup.pet
    assert pet and pet.ready, 'model did not become ready'
    QTest.qWait(400)

    def frame():
        pet.view.update()
        QTest.qWait(180)
        buffer = QBuffer()
        buffer.open(QIODevice.WriteOnly)
        pet.view.grab().toImage().save(buffer, 'PNG')
        return bytes(buffer.data())

    for name, low, high in CHECKS:
        pet.view.model.SetParamById(name, low)
        first = frame()
        pet.view.model.SetParamById(name, high)
        second = frame()
        same = first == second
        print(f'{name:18} {"未绑定（画面没有变化）" if same else "已绑定（画面随参数变化）"}', flush=True)

    pet.shutdown()
    setup.shutdown()
    setup.close()
    QTest.qWait(100)
