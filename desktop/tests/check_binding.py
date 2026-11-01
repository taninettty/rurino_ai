"""Fail unless each required native parameter changes actual Cubism-rendered pixels.

No application animation, physics timestep, auto-blink, auto-breath, or image warp.
Also check endpoints/ranges and repeatability so timing cannot masquerade as binding.
"""
from pathlib import Path
import sys
import numpy as np
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QSurfaceFormat
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QOpenGLWidget
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from model_support import validate_model
from contextlib import redirect_stdout
from io import StringIO
# Only silence the library import advertisement; retain SDK diagnostics and failures.
with redirect_stdout(StringIO()):
    import live2d

REQUIRED = {'ParamEyeLOpen': (0, 1), 'ParamEyeROpen': (0, 1),
            'ParamMouthOpenY': (0, 1), 'ParamAngleX': (-30, 30),
            'ParamAngleY': (-30, 30), 'ParamAngleZ': (-30, 30),
            'ParamBreath': (0, 1)}

def main():
    path, _ = validate_model(sys.argv[1])
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
    fmt = QSurfaceFormat(); fmt.setAlphaBufferSize(8); fmt.setVersion(2, 1)
    QSurfaceFormat.setDefaultFormat(fmt)
    app = QApplication([])
    live2d.setLogLevel(live2d.LogLevels.LV_ERROR)
    live2d.init()

    class View(QOpenGLWidget):
        def __init__(self):
            super().__init__(); self.model = None; self.pose = {}; self.resize(768, 768)
        def initializeGL(self):
            live2d.glInit(); self.model = live2d.Model(); self.model.LoadModelJson(str(path))
            self.model.SetAutoBlink(False); self.model.SetAutoBreath(False)
        def resizeGL(self, w, h):
            if self.model: self.model.Resize(w, h)
        def paintGL(self):
            live2d.clearBuffer(0, 0, 0, 0)
            if self.model:
                self.model.ResetAllParameters()
                for key, value in self.pose.items(): self.model.SetParamById(key, value)
                self.model.SaveParameters(); self.model.Update(0); self.model.Draw()
        def frame(self, pose):
            self.pose = pose
            q = self.grabFramebuffer().convertToFormat(QImage.Format_RGBA8888)
            data = q.bits(); data.setsize(q.byteCount())
            rgba = np.frombuffer(data, np.uint8).reshape(q.height(), q.width(), 4).copy()
            # Compare visible, premultiplied color and alpha, not hidden transparent RGB.
            rgb = rgba[:, :, :3].astype(np.float32) * (rgba[:, :, 3:4] / 255.)
            return np.concatenate([rgb, rgba[:, :, 3:4]], axis=2)
    view = View(); view.show(); QTest.qWait(500)
    failed = []
    try:
        model = view.model
        assert model is not None, 'SDK model initialization failed'
        ids = model.GetParamIds()
        for key, (low, high) in REQUIRED.items():
            if key not in ids:
                print(f'{key}: FAIL 参数不存在'); failed.append(key); continue
            if model.GetParamMinById(key) > low or model.GetParamMaxById(key) < high:
                print(f'{key}: FAIL 参数范围不包含 {low}..{high}'); failed.append(key); continue
            a = view.frame({key: low}); b = view.frame({key: high}); again = view.frame({key: low})
            changed = int(np.count_nonzero(np.max(np.abs(a-b), axis=2) > 2))
            unstable = int(np.count_nonzero(np.max(np.abs(a-again), axis=2) > 2))
            if changed < 20 or unstable:
                print(f'{key}: FAIL 未绑定或非确定性变化 (changed_pixels={changed}, repeat_diff={unstable})')
                failed.append(key)
            else:
                print(f'{key}: 已绑定（画面随参数变化） changed_pixels={changed}')
        print('FAIL: ' + ', '.join(failed) if failed else 'PASS: all 7 required parameters change native rendered pixels')
    finally:
        view.makeCurrent()
        if view.model: view.model.DestroyRenderer(); view.model = None
        view.doneCurrent(); view.close(); live2d.dispose()
    return bool(failed)

if __name__ == '__main__':
    sys.exit(main())
