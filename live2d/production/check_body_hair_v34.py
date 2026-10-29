"""Validate exported waist sway, tail composition and real SDK hair physics."""
import sys,json,math,itertools,hashlib,subprocess,os,shutil
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QSurfaceFormat,QImage
from PyQt5.QtWidgets import QApplication,QOpenGLWidget
from PyQt5.QtTest import QTest
import live2d
path=Path(sys.argv[1]).resolve();out=path.parent.parent/'qa-body';out.mkdir(exist_ok=True)
data=json.loads(path.read_text());bare=json.loads(path.read_text());bare['FileReferences'].pop('Physics');bare['FileReferences'].pop('Motions',None)
qa_path=path.parent/'__qa_no_physics.model3.json';qa_path.write_text(json.dumps(bare))
QApplication.setAttribute(Qt.AA_ShareOpenGLContexts);fmt=QSurfaceFormat();fmt.setAlphaBufferSize(8);fmt.setVersion(2,1);QSurfaceFormat.setDefaultFormat(fmt)
app=QApplication([]);live2d.init()
class View(QOpenGLWidget):
 def __init__(self):
  super().__init__();self.model=None;self.resize(900,733)
 def initializeGL(self):
  live2d.glInit();self.model=live2d.Model();self.model.LoadModelJson(str(qa_path));self.model.SetAutoBlink(False);self.model.SetAutoBreath(False)
 def resizeGL(self,w,h):
  if self.model:self.model.Resize(w,h)
 def paintGL(self):
  if self.model:live2d.clearBuffer(0,0,0,0);self.model.Draw()
v=View();v.show();QTest.qWait(500)
ids=v.model.GetDrawableIds();ppu=v.model.GetCanvasSizePixel()[1]/v.model.GetCanvasSize()[1]
params=['ParamHairSmallL','ParamHairSmallR','ParamHairSide','ParamHairBack'];names=['Small_L','Small_R','Large_L','Large_R']
def step(body,tails=(0,0,0,0),dt=0):
 v.makeCurrent();v.model.ResetAllParameters();v.model.SetParamById('ParamBodyAngleZ',float(body))
 for p,x in zip(params,tails):v.model.SetParamById(p,float(x))
 v.model.SaveParameters();v.model.Update(dt);live2d.clearBuffer(0,0,0,0);v.model.Draw();v.doneCurrent()
def capture():
 q=v.grabFramebuffer().convertToFormat(QImage.Format_RGBA8888);bits=q.bits();bits.setsize(q.byteCount());return Image.frombytes('RGBA',(q.width(),q.height()),bytes(bits))
def verts():return [np.array(v.model.GetDrawableVertices(i)).reshape(-1,2) for i in range(len(ids))]
def areas(x,i):
 t=x[np.array(v.model.GetDrawableIndices(i)).reshape(-1,3)];a=t[:,1]-t[:,0];b=t[:,2]-t[:,0];return a[:,0]*b[:,1]-a[:,1]*b[:,0]
def fit(a,b):
 ac=a.mean(0);bc=b.mean(0);u,s,vt=np.linalg.svd((a-ac).T@(b-bc));r=u@vt;return r,bc-ac@r
step(0);base=verts();capture().save(out/'neutral.png');head=ids.index('FacePaint_AfterCheekRecovery_SOURCE')
report={'model':path.name,'moc_sha256':hashlib.sha256((path.parent/data['FileReferences']['Moc']).read_bytes()).hexdigest(),'drawables':len(ids),'samples':[]}
poses=list(itertools.product([-1,1],repeat=4))+[(0,0,0,0)];images={}
for tails in poses:
 step(0,tails);local=verts()
 for body in [-10,0,10]:
  step(body,tails);now=verts();r,t=fit(local[head],now[head]);err=max(float(np.linalg.norm(a@r+t-b,axis=1).max()*ppu) for a,b in zip(local,now))
  flips=sum(int((areas(a,i)*areas(b,i)<-1e-14).sum()) for i,(a,b) in enumerate(zip(base,now)))
  angle=float(math.degrees(math.atan2(r[0,1],r[0,0])))
  assert err<.01,(body,tails,err)
  assert flips==0,(body,tails,flips)
  assert abs(abs(angle)-abs(body)*.3)<.01,(body,angle)
  report['samples'].append({'body':body,'tails':tails,'rigid_sway_degrees':angle,'max_composition_error_px':err,'flipped_triangles':flips})
  if tails==(0,0,0,0):images[body]=capture()
sheet=Image.new('RGB',(1350,570),'#e7eaf0')
for k,b in enumerate([-10,0,10]):
 im=images[b];im.thumbnail((450,520));sheet.paste(im,(k*450,32),im);ImageDraw.Draw(sheet).text((k*450+12,10),f'Body Z {b:+g}, lean {b*.3:+g} deg',fill='#202633')
sheet.save(out/'body-sway-poses.jpg',quality=94)
# Reload with the actual exported physics settings. Advance fixed simulation time;
# frames record SDK output. Tail values are never assigned by an animation curve.
v.makeCurrent();v.model.DestroyRenderer();v.model=live2d.Model();v.model.LoadModelJson(str(path));v.model.Resize(v.width(),v.height());v.model.SetAutoBlink(False);v.model.SetAutoBreath(False);v.doneCurrent()
frames=[];values=[]
ffmpeg=os.environ.get('FFMPEG',shutil.which('ffmpeg') or str(Path('tmp/ffmpeg/ffmpeg').resolve()))
encoder=subprocess.Popen([ffmpeg,'-hide_banner','-loglevel','error','-y','-f','rawvideo','-pixel_format','rgb24','-video_size','550x448','-framerate','30','-i','-','-an','-c:v','libx264','-crf','16','-pix_fmt','yuv420p','-movflags','+faststart',str(out/'body-hair-physics.mp4')],stdin=subprocess.PIPE)
for f in range(960):
 t=f/60
 # Two smooth 6-second cycles, followed by a 4-second rest.
 body=8*math.sin(2*math.pi*t/6) if f<720 else 0
 step(body,dt=1/60)
 row=[v.model.GetParamValueById(p) for p in params];values.append(row)
 assert np.all(np.isfinite(row)) and max(abs(x) for x in row)<=1.001,(f,row)
 if f%2==0:
  im=capture().resize((550,448),Image.Resampling.LANCZOS);bg=Image.new('RGB',im.size,'#e7eaf0');bg.paste(im,(0,0),im);encoder.stdin.write(bg.tobytes())
  if f in [0,100,280,460,700,940]:bg.save(out/f'physics-frame-{f:04d}.png')
encoder.stdin.close();assert encoder.wait()==0

values=np.array(values);peak=np.max(np.abs(values),axis=0);rest=np.max(np.abs(values[-60:]),axis=0)
assert np.all(peak>.01),peak
assert np.all(rest<.04),(peak,rest)
report['physics']={'frames':960,'fps':60,'body_input_peak':8,'peak_outputs':dict(zip(params,peak.tolist())),'last_second_max_abs_outputs':dict(zip(params,rest.tolist())),'nonzero_and_settles':True,'animation':'Two body sway cycles followed by rest; tails are driven only by exported Cubism physics.'}
report['passed']=True
(out/'body-hair-report.json').write_text(json.dumps(report,indent=2))
print(json.dumps({'passed':True,'samples':len(report['samples']),'physics':report['physics']}),flush=True)
v.makeCurrent();v.model.DestroyRenderer();v.model=None;v.doneCurrent();v.close();live2d.dispose();qa_path.unlink()
