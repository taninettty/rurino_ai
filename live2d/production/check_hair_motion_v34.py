"""Check four independent tail bindings in a real exported Cubism model.

Requires PyQt5, live2d-py, Pillow, numpy and an OpenGL display.
Optional second argument compares the neutral state with an earlier runtime.
"""
import sys,json,math,hashlib,itertools
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QSurfaceFormat,QImage
from PyQt5.QtWidgets import QApplication,QOpenGLWidget
from PyQt5.QtTest import QTest
import live2d
path=Path(sys.argv[1]).resolve();out=path.parent.parent/'qa-hair';out.mkdir(exist_ok=True)
params=['ParamHairSmallL','ParamHairSmallR','ParamHairSide','ParamHairBack']
names=['Small_L','Small_R','Large_L','Large_R']
QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
fmt=QSurfaceFormat();fmt.setAlphaBufferSize(8);fmt.setVersion(2,1);QSurfaceFormat.setDefaultFormat(fmt)
app=QApplication([]);live2d.init()
class View(QOpenGLWidget):
 def __init__(self):
  super().__init__();self.pose=[0]*4;self.model=None;self.resize(1200,978)
 def initializeGL(self):
  live2d.glInit();self.model=live2d.Model();self.model.LoadModelJson(str(path));self.model.SetAutoBlink(False);self.model.SetAutoBreath(False)
 def resizeGL(self,w,h):
  if self.model:self.model.Resize(w,h)
 def paintGL(self):
  if not self.model:return
  live2d.clearBuffer(0,0,0,0);self.model.ResetAllParameters()
  for name,value in zip(params,self.pose):self.model.SetParamById(name,value)
  self.model.SaveParameters();self.model.Update(0);self.model.Draw()
v=View();v.show();QTest.qWait(600)
ids=v.model.GetDrawableIds();ppu=v.model.GetCanvasSizePixel()[1]/v.model.GetCanvasSize()[1]
def pose(values):
 v.pose=values;v.update();QTest.qWait(30)
 q=v.grabFramebuffer().convertToFormat(QImage.Format_RGBA8888);bits=q.bits();bits.setsize(q.byteCount())
 return Image.frombytes('RGBA',(q.width(),q.height()),bytes(bits))
def vertices():return [np.array(v.model.GetDrawableVertices(i)).reshape(-1,2) for i in range(len(ids))]
def area(x,i):
 t=x[np.array(v.model.GetDrawableIndices(i)).reshape(-1,3)];a=t[:,1]-t[:,0];b=t[:,2]-t[:,0]
 return a[:,0]*b[:,1]-a[:,1]*b[:,0]
neutral=pose([0]*4);base=vertices();neutral.save(out/'neutral.png')
pairs={}
for name in names:
 ii,ci=ids.index('Ink_'+name),ids.index(name);shared=[]
 for j,point in enumerate(base[ii]):
  d=np.linalg.norm(base[ci]-point,axis=1);k=int(d.argmin())
  if d[k]<1e-7:shared.append((j,k))
 assert shared;pairs[name]=(ii,ci,shared)
ref=json.loads(path.read_text())['FileReferences']
report={'model':path.name,'moc_sha256':hashlib.sha256((path.parent/ref['Moc']).read_bytes()).hexdigest(),'parameter_mapping':dict(zip(names,params)),'drawables':len(ids),'samples':[]}
poses=set(itertools.product([-1,0,1],repeat=4))
for k in range(4):
 for x in np.linspace(-1,1,9):
  p=[0]*4;p[k]=float(x);poses.add(tuple(p))
images={}
for p in sorted(poses):
 im=pose(p);current=vertices();moved=[];expected=set()
 for name,value in zip(names,p):
  if value:expected.update([name,'Ink_'+name])
 for i,(b,c) in enumerate(zip(base,current)):
  d=np.linalg.norm(c-b,axis=1)*ppu
  if d.max()<.001:continue
  root=b[:,1]>=b[:,1].max()-np.ptp(b[:,1])*.1
  moved.append({'id':ids[i],'max_displacement_source_px':float(d.max()),'top10pct_max_source_px':float(d[root].max()),'flipped_triangles':int(np.sum(area(b,i)*area(c,i)<-1e-14))})
 assert {m['id'] for m in moved}==expected,(p,moved)
 assert all(m['flipped_triangles']==0 for m in moved),(p,moved)
 assert all(m['top10pct_max_source_px']<.01 for m in moved),(p,moved)
 alignment={}
 for name,(ii,ci,shared) in pairs.items():
  err=max(float(np.linalg.norm((current[ii][j]-base[ii][j])-(current[ci][k]-base[ci][k]))*ppu) for j,k in shared)
  assert err<.01;alignment[name]=err
 report['samples'].append({'pose':list(p),'moved':moved,'ink_color_displacement_error_px':alignment})
 if p in [(-1,1,-1,1),(0,0,0,0),(1,-1,1,-1)]:images[p]=im
report['sample_checks_passed']=True
if len(sys.argv)>2:
 old=Path(sys.argv[2]).resolve();pose([0]*4);v.makeCurrent();v.model.DestroyRenderer();v.model=None
 v.model=live2d.Model();v.model.LoadModelJson(str(old));v.model.SetAutoBlink(False);v.model.SetAutoBreath(False);v.model.Resize(v.width(),v.height());v.doneCurrent()
 oldim=pose([0]*4);oldids=v.model.GetDrawableIds();oldv=vertices()
 assert ids==oldids
 delta=max(float(np.abs(a-b).max()) for a,b in zip(base,oldv))*ppu
 imdelta=int(np.abs(np.asarray(neutral).astype(int)-np.asarray(oldim).astype(int)).max())
 diff=np.abs(np.asarray(neutral).astype(int)-np.asarray(oldim).astype(int));count=int((diff.max(2)>3).sum());mean=float(diff.mean());neutral.save(out/'neutral-new.png');oldim.save(out/'neutral-reference.png')
 report['neutral_comparison']={'reference':old.name,'max_vertex_difference_px':delta,'max_pixel_difference':imdelta,'mean_pixel_difference':mean,'pixels_over_3':count}
 print(json.dumps(report['neutral_comparison']),flush=True)
 assert delta<.001 and mean<.001 and count<20,report['neutral_comparison']
 v.makeCurrent();v.model.DestroyRenderer();v.model=live2d.Model();v.model.LoadModelJson(str(path));v.model.SetAutoBlink(False);v.model.SetAutoBreath(False);v.model.Resize(v.width(),v.height());v.doneCurrent()
sheet=Image.new('RGB',(1500,690),'#e7eaf0')
for i,key in enumerate([(-1,1,-1,1),(0,0,0,0),(1,-1,1,-1)]):
 im=images[key].crop((50,0,1150,950));im.thumbnail((500,630));sheet.paste(im,(i*500,38),im)
 ImageDraw.Draw(sheet).text((i*500+12,10),'S-L/R L-L/R: '+str(key),fill='#202633')
sheet.save(out/'hair-runtime-poses.jpg',quality=95)
frames=[]
for f in range(48):
 t=2*math.pi*f/48
 im=pose([math.sin(t+.25)*.8,math.sin(t-.2)*.8,math.sin(t-.5)*.8,math.sin(t-.9)*.8]).crop((50,0,1150,950));im.thumbnail((550,475))
 bg=Image.new('RGB',im.size,'#e7eaf0');bg.paste(im,(0,0),im);frames.append(bg.convert("P",palette=Image.Palette.ADAPTIVE,colors=128))
frames[0].save(out/'hair-runtime-sway.gif',save_all=True,append_images=frames[1:],duration=80,loop=0)
report['preview_note']='Parameter-driven demonstration, not a physics simulation.'
(out/'hair-runtime-report.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'samples':len(report['samples']),'passed':True,'output':str(out)}))
v.makeCurrent();v.model.DestroyRenderer();v.model=None;v.doneCurrent();v.close();live2d.dispose()
