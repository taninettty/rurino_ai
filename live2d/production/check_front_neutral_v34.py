"""Render the actual frontal moc3 and compare it with the saved PSD composite."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QSurfaceFormat
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QOpenGLWidget
import live2d

path = Path(sys.argv[1]).resolve()
reference = Path(sys.argv[2]).resolve()
out = path.parent.parent/'qa-runtime'
out.mkdir(exist_ok=True)
QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
fmt = QSurfaceFormat(); fmt.setAlphaBufferSize(8); fmt.setVersion(2,1)
QSurfaceFormat.setDefaultFormat(fmt)
app = QApplication([]); live2d.init()


class View(QOpenGLWidget):
    def __init__(self):
        super().__init__(); self.model=None; self.resize(1024,1024)
    def initializeGL(self):
        live2d.glInit(); self.model=live2d.Model()
        self.model.LoadModelJson(str(path))
        self.model.SetAutoBlink(False); self.model.SetAutoBreath(False)
    def resizeGL(self,w,h):
        if self.model: self.model.Resize(w,h)
    def paintGL(self):
        if self.model:
            live2d.clearBuffer(0,0,0,0)
            self.model.ResetAllParameters(); self.model.SaveParameters()
            self.model.Update(0); self.model.Draw()


v=View(); v.show(); QTest.qWait(600)
q=v.grabFramebuffer().convertToFormat(QImage.Format_RGBA8888)
bits=q.bits(); bits.setsize(q.byteCount())
actual=Image.frombytes('RGBA',(q.width(),q.height()),bytes(bits))
actual.save(out/'front-runtime.png')
ids=v.model.GetDrawableIds()
meshes=[]
for i,name in enumerate(ids):
    verts=np.array(v.model.GetDrawableVertices(i)).reshape(-1,2)
    indices=np.array(v.model.GetDrawableIndices(i)).reshape(-1,3)
    assert np.isfinite(verts).all() and len(verts)>=3 and len(indices)>0
    assert indices.min()>=0 and indices.max()<len(verts)
    meshes.append({'id':name,'vertices':len(verts),'triangles':len(indices)})
expected=Image.open(reference).convert('RGBA').resize(actual.size,Image.Resampling.LANCZOS)
a=np.array(actual);e=np.array(expected)
diff=np.abs(a.astype('int16')-e.astype('int16'))
opaque=(a[:,:,3]>250)&(e[:,:,3]>250)
white=[]
for im in (expected,actual):
    bg=Image.new('RGB',im.size,'#e7eaf0');bg.paste(im,(0,0),im);white.append(bg)
sheet=Image.new('RGB',(1200,630),'#e7eaf0');d=ImageDraw.Draw(sheet)
for i,(label,im) in enumerate(zip(('PSD composite','Actual Cubism SDK render'),white)):
    sheet.paste(im.resize((600,600),Image.Resampling.LANCZOS),(600*i,30))
    d.text((600*i+12,10),label,fill='#202633')
sheet.save(out/'front-psd-runtime.jpg',quality=96)
data=json.loads(path.read_text())
report={'model':path.name,'moc3_sha256':hashlib.sha256((path.parent/data['FileReferences']['Moc']).read_bytes()).hexdigest(),
        'canvas_pixels':v.model.GetCanvasSizePixel(),'canvas_units':v.model.GetCanvasSize(),
        'drawable_count':len(ids),'meshes':meshes,'parameter_count':v.model.GetParamCount(),
        'opaque_rgb_mean_abs_difference':float(diff[:,:,:3][opaque].mean()),
        'alpha_mean_abs_difference':float(diff[:,:,3].mean()),
        'reference_alpha_bbox':expected.getbbox(),'runtime_alpha_bbox':actual.getbbox(),
        'scope':'neutral render and mesh validity only; not an animation or Windows acceptance test'}
expected_count=int(sys.argv[3]) if len(sys.argv)>3 else 29
assert len(ids)==expected_count, (len(ids),expected_count)
assert report['opaque_rgb_mean_abs_difference']<5,report
assert report['alpha_mean_abs_difference']<2,report
report['passed']=True
(out/'front-runtime-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:x for k,x in report.items() if k!='meshes'},indent=2))
v.makeCurrent();v.model.DestroyRenderer();v.model=None;v.doneCurrent();v.close();live2d.dispose()
