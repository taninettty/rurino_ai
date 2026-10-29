"""Render the exported trial and measure deformation in Cubism runtime coordinates."""
import json, math, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QSurfaceFormat, QImage
from PyQt5.QtWidgets import QApplication, QOpenGLWidget
from PyQt5.QtTest import QTest
import live2d

path = Path(sys.argv[1]).resolve()
out = path.parent.parent / 'qa'
out.mkdir(exist_ok=True)
QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
fmt = QSurfaceFormat(); fmt.setAlphaBufferSize(8); fmt.setVersion(2, 1)
QSurfaceFormat.setDefaultFormat(fmt)
app = QApplication([]); live2d.init()
class View(QOpenGLWidget):
    def __init__(self):
        super().__init__(); self.value = 0.; self.model = None; self.resize(1000, 815)
    def initializeGL(self):
        live2d.glInit(); self.model = live2d.Model(); self.model.LoadModelJson(str(path))
        self.model.SetAutoBlink(False); self.model.SetAutoBreath(False)
    def resizeGL(self, w, h):
        if self.model: self.model.Resize(w, h)
    def paintGL(self):
        if not self.model: return
        live2d.clearBuffer(0, 0, 0, 0); self.model.ResetAllParameters()
        self.model.SetParamById('ParamHairSmallR', self.value)
        self.model.SaveParameters(); self.model.Update(0); self.model.Draw()
v = View(); v.show(); QTest.qWait(1000)
assert 'ParamHairSmallR' in v.model.GetParamIds()
ids = v.model.GetDrawableIds()
def pose(value):
    v.value = value; v.update(); QTest.qWait(70)
    q = v.grabFramebuffer().convertToFormat(QImage.Format_RGBA8888)
    ptr = q.bits(); ptr.setsize(q.byteCount())
    return Image.frombytes('RGBA', (q.width(), q.height()), bytes(ptr))
def vertices():
    return [np.array(v.model.GetDrawableVertices(i)).reshape(-1, 2) for i in range(len(ids))]
def areas(verts, index):
    tri = verts[np.array(v.model.GetDrawableIndices(index)).reshape(-1, 3)]
    ab = tri[:,1] - tri[:,0]; ac = tri[:,2] - tri[:,0]
    return ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0]
neutral = pose(0); neutral.save(out/'hair-neutral.png'); base = vertices()
report = {'model': path.name, 'parameter': 'ParamHairSmallR', 'canvas_pixels':v.model.GetCanvasSizePixel(), 'canvas_units':v.model.GetCanvasSize(), 'drawables':len(ids), 'samples':[]}
ppu = 2816.0
frames = {}
for value in [-1, -.75, -.5, -.25, 0, .25, .5, .75, 1]:
    im = pose(value); current = vertices(); moved = []
    for i, (b, c) in enumerate(zip(base, current)):
        delta = np.linalg.norm(c-b, axis=1)*ppu
        if delta.max() < .001: continue
        root = b[:,1] >= b[:,1].max() - np.ptp(b[:,1])*.10
        tip = b[:,1] <= b[:,1].min() + np.ptp(b[:,1])*.15
        a0, a1 = areas(b, i), areas(c, i)
        moved.append({'id':ids[i], 'max_displacement_source_px':float(delta.max()), 'top10pct_max_source_px':float(delta[root].max()), 'bottom15pct_max_source_px':float(delta[tip].max()), 'flipped_triangles':int(np.sum(a0*a1 < -1e-14))})
    assert {m['id'] for m in moved} == ({'Small_R', 'Ink_Small_R'} if value else set())
    assert all(m['flipped_triangles'] == 0 for m in moved)
    assert all(m['top10pct_max_source_px'] < 6 for m in moved)
    # Compare displacement at vertices shared by colour and contour meshes.
    ink_i, col_i = ids.index('Ink_Small_R'), ids.index('Small_R')
    pairs = []
    for j, point in enumerate(base[ink_i]):
        d = np.linalg.norm(base[col_i] - point, axis=1); k = int(d.argmin())
        if d[k] < 1e-7: pairs.append((j, k))
    errors = [float(np.linalg.norm((current[ink_i][j]-base[ink_i][j])-(current[col_i][k]-base[col_i][k]))*ppu) for j,k in pairs]
    assert errors and max(errors) < .01
    report['samples'].append({'value':value, 'moved':moved, 'shared_vertices_checked':len(errors), 'shared_vertex_displacement_error_source_px':max(errors)})
    if value in [-1, 0, 1]:
        im.save(out/f'hair-pose-{value:+g}.png'); frames[value] = im
(out/'hair-runtime-report.json').write_text(json.dumps(report, indent=2))
report['sample_checks_passed'] = True
(out/'hair-runtime-report.json').write_text(json.dumps(report, indent=2))
# Full model sheet: keep framing identical across poses.
sheet = Image.new('RGB', (1500, 440), '#e7eaf0')
for i, value in enumerate([-1, 0, 1]):
    im = frames[value].copy(); im.thumbnail((500, 408))
    sheet.paste(im, (i*500, 32), im)
    ImageDraw.Draw(sheet).text((i*500+12, 10), f'ParamHairSmallR = {value:+g}', fill='#202633')
sheet.save(out/'hair-runtime-poses.jpg', quality=94)
# GIF shows rendered runtime frames, no image warping.
anim = []
for f in range(48):
    im = pose(math.sin(2*math.pi*f/48)); im.thumbnail((700, 571))
    bg = Image.new('RGB', im.size, '#e7eaf0'); bg.paste(im, (0,0), im); anim.append(bg)
closeups = [im.crop((335, 20, 545, 225)).resize((420, 410)) for im in anim]
closeups[0].save(out/'hair-runtime-closeup.gif', save_all=True, append_images=closeups[1:], duration=65, loop=0)
anim[0].save(out/'hair-runtime-sway.gif', save_all=True, append_images=anim[1:], duration=65, loop=0)
print(json.dumps(report, indent=2))
v.makeCurrent(); v.model.DestroyRenderer(); v.model = None; v.doneCurrent(); v.close(); live2d.dispose()
