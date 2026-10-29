"""Validate independent and combined small-tail deformation in the exported Cubism model."""
import sys, json, math, hashlib
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QSurfaceFormat, QImage
from PyQt5.QtWidgets import QApplication, QOpenGLWidget
from PyQt5.QtTest import QTest
import live2d
path=Path(sys.argv[1]).resolve();out=path.parent.parent/'qa-smalltails';out.mkdir(exist_ok=True)
QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
fmt=QSurfaceFormat();fmt.setAlphaBufferSize(8);fmt.setVersion(2,1);QSurfaceFormat.setDefaultFormat(fmt)
app=QApplication([]);live2d.init()
class View(QOpenGLWidget):
 def __init__(self):
  super().__init__();self.pose=(0,0);self.model=None;self.resize(1000,815)
 def initializeGL(self):
  live2d.glInit();self.model=live2d.Model();self.model.LoadModelJson(str(path));self.model.SetAutoBlink(False);self.model.SetAutoBreath(False)
 def resizeGL(self,w,h):
  if self.model:self.model.Resize(w,h)
 def paintGL(self):
  if not self.model:return
  live2d.clearBuffer(0,0,0,0);self.model.ResetAllParameters()
  for name,value in zip(['ParamHairSmallL','ParamHairSmallR'],self.pose):self.model.SetParamById(name,value)
  self.model.SaveParameters();self.model.Update(0);self.model.Draw()
v=View();v.show();QTest.qWait(1000)
assert {'ParamHairSmallL','ParamHairSmallR'} <= set(v.model.GetParamIds())
ids=v.model.GetDrawableIds();ppu=v.model.GetCanvasSizePixel()[1]/v.model.GetCanvasSize()[1]
def pose(l,r):
 v.pose=(l,r);v.update();QTest.qWait(80)
 q=v.grabFramebuffer().convertToFormat(QImage.Format_RGBA8888);bits=q.bits();bits.setsize(q.byteCount())
 return Image.frombytes('RGBA',(q.width(),q.height()),bytes(bits))
def vertices():return [np.array(v.model.GetDrawableVertices(i)).reshape(-1,2) for i in range(len(ids))]
def area(x,i):
 t=x[np.array(v.model.GetDrawableIndices(i)).reshape(-1,3)];a=t[:,1]-t[:,0];b=t[:,2]-t[:,0]
 return a[:,0]*b[:,1]-a[:,1]*b[:,0]
neutral=pose(0,0);base=vertices();neutral.save(out/'neutral.png')
pairs={}
for side in ['L','R']:
 ii,ci=ids.index('Ink_Small_'+side),ids.index('Small_'+side);shared=[]
 for j,point in enumerate(base[ii]):
  d=np.linalg.norm(base[ci]-point,axis=1);k=int(d.argmin())
  if d[k]<1e-7:shared.append((j,k))
 assert shared;pairs[side]=(ii,ci,shared)
report={'model':path.name,'moc_sha256':hashlib.sha256(path.with_suffix('').with_suffix('.moc3').read_bytes()).hexdigest(),'canvas_pixels':v.model.GetCanvasSizePixel(),'drawables':len(ids),'parameters':v.model.GetParamIds(),'samples':[]}
poses=sorted(set([(x,0) for x in np.linspace(-1,1,9)]+[(0,x) for x in np.linspace(-1,1,9)]+[(x,y) for x in [-1,-.5,0,.5,1] for y in [-1,-.5,0,.5,1]]))
images={}
for left,right in poses:
 im=pose(float(left),float(right));current=vertices();moved=[]
 for i,(b,c) in enumerate(zip(base,current)):
  d=np.linalg.norm(c-b,axis=1)*ppu
  if d.max()<.001:continue
  root=b[:,1]>=b[:,1].max()-np.ptp(b[:,1])*.1
  moved.append({'id':ids[i],'max_displacement_source_px':float(d.max()),'top10pct_max_source_px':float(d[root].max()),'flipped_triangles':int(np.sum(area(b,i)*area(c,i)<-1e-14))})
 expected=set()
 for side,value in [('L',left),('R',right)]:
  if value:expected.update(['Small_'+side,'Ink_Small_'+side])
 assert {m['id'] for m in moved}==expected,(left,right,moved)
 assert all(m['flipped_triangles']==0 for m in moved)
 assert all(m['top10pct_max_source_px']<6 for m in moved),(left,right,moved)
 alignment={}
 for side,(ii,ci,shared) in pairs.items():
  err=max(float(np.linalg.norm((current[ii][j]-base[ii][j])-(current[ci][k]-base[ci][k]))*ppu) for j,k in shared)
  assert err<.01
  alignment[side]={'shared_vertices':len(shared),'max_displacement_error_source_px':err}
 report['samples'].append({'left':float(left),'right':float(right),'moved':moved,'alignment':alignment})
 if (left,right) in [(-1,1),(0,0),(1,-1)]:images[left,right]=im
report['sample_checks_passed']=True
(out/'smalltails-runtime-report.json').write_text(json.dumps(report,indent=2))
sheet=Image.new('RGB',(1500,380),'#e7eaf0')
for i,key in enumerate([(-1,1),(0,0),(1,-1)]):
 im=images[key].crop((200,0,800,420));im.thumbnail((500,350));sheet.paste(im,(i*500,30),im)
 ImageDraw.Draw(sheet).text((i*500+12,10),f'L={key[0]:+g} R={key[1]:+g}',fill='#202633')
sheet.save(out/'smalltails-runtime-poses.jpg',quality=94)
frames=[]
for f in range(48):
 t=2*math.pi*f/48
 im=pose(math.sin(t)*.9, math.sin(t-.45)*.9).crop((200,0,800,440));im.thumbnail((660,484))
 bg=Image.new('RGB',im.size,'#e7eaf0');bg.paste(im,(0,0),im);frames.append(bg)
frames[0].save(out/'smalltails-runtime-sway.gif',save_all=True,append_images=frames[1:],duration=65,loop=0)
print(json.dumps({'samples':len(report['samples']),'passed':True,'output':str(out)}))
v.makeCurrent();v.model.DestroyRenderer();v.model=None;v.doneCurrent();v.close();live2d.dispose()
