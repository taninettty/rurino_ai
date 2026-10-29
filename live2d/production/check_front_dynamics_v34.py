"""Render exported frontal Cubism geometry; inspect isolation and capture an actual SDK preview."""
import json, math, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage, QSurfaceFormat
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QOpenGLWidget
import live2d

path=Path(sys.argv[1]).resolve(); out=path.parent.parent/'qa-dynamics';out.mkdir(exist_ok=True)
QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
fmt=QSurfaceFormat();fmt.setAlphaBufferSize(8);fmt.setVersion(2,1);QSurfaceFormat.setDefaultFormat(fmt)
app=QApplication([]);live2d.init()
class View(QOpenGLWidget):
 def __init__(self):
  super().__init__();self.model=None;self.pose={};self.resize(768,768)
 def initializeGL(self):
  live2d.glInit();self.model=live2d.Model();self.model.LoadModelJson(str(path));self.model.SetAutoBlink(False);self.model.SetAutoBreath(False)
 def resizeGL(self,w,h):
  if self.model:self.model.Resize(w,h)
 def paintGL(self):
  if self.model:
   live2d.clearBuffer(0,0,0,0);self.model.ResetAllParameters()
   for k,x in self.pose.items():self.model.SetParamById(k,x)
   self.model.SaveParameters();self.model.Update(0);self.model.Draw()
v=View();v.show();QTest.qWait(500)
ids=v.model.GetDrawableIds()
def capture(pose):
 v.pose=pose;v.update();QTest.qWait(5)
 q=v.grabFramebuffer().convertToFormat(QImage.Format_RGBA8888);bits=q.bits();bits.setsize(q.byteCount())
 im=Image.frombytes('RGBA',(q.width(),q.height()),bytes(bits))
 verts={s:np.array(v.model.GetDrawableVertices(i)).reshape(-1,2).copy()*2048 for i,s in enumerate(ids)}
 return im,verts
neutral,base=capture({});neutral.save(out/'neutral.png')
indices={s:np.array(v.model.GetDrawableIndices(i)).reshape(-1,3) for i,s in enumerate(ids)}
def areas(p,s):
 a,b,c=np.transpose(p[indices[s]],(1,0,2));ab=b-a;ac=c-a;return ab[:,0]*ac[:,1]-ab[:,1]*ac[:,0]
poses={'neutral':{},'blink':{'ParamEyeLOpen':0,'ParamEyeROpen':0},'half_blink':{'ParamEyeLOpen':.5,'ParamEyeROpen':.5},'left_blink':{'ParamEyeLOpen':0},'right_blink':{'ParamEyeROpen':0},'mouth_open':{'ParamMouthOpenY':1},'sway_left':{'ParamBodyAngleZ':-10},'sway_right':{'ParamBodyAngleZ':10},'breath':{'ParamBreath':1},'tail_left_min':{'ParamHairSide':-1},'tail_left_max':{'ParamHairSide':1},'tail_right_min':{'ParamHairBack':-1},'tail_right_max':{'ParamHairBack':1},'combined':{'ParamBodyAngleZ':6,'ParamBreath':.8,'ParamHairSide':.5,'ParamHairBack':-.5,'ParamMouthOpenY':.5,'ParamEyeLOpen':.6,'ParamEyeROpen':.6}}
report={'model':path.name,'drawables':len(ids),'poses':{},'limits':['No yaw, pitch, forward/back lean or small-tail binding','This controlled preview uses explicit parameters, not live audio or Windows']}
images={}
for label,pose in poses.items():
 im,points=capture(pose);im.save(out/(label+'.png'));images[label]=im
 changed={s:round(float(np.linalg.norm(points[s]-base[s],axis=1).max()),5) for s in ids if np.max(np.abs(points[s]-base[s]))>.001}
 flips={s:int(np.count_nonzero((areas(points[s],s)*areas(base[s],s)<0)&(abs(areas(base[s],s))>.1))) for s in ids}
 assert all(np.isfinite(x).all() for x in points.values()),label
 assert not any(flips.values()),(label,flips)
 report['poses'][label]={'changed_meshes_max_pixels':changed,'new_triangle_flips':sum(flips.values())}
 if label.startswith('tail_'):
  s='Ponytail_L' if 'left' in label else 'Ponytail_R';dy=base[s][:,1];root=dy>dy.max()-1
  report['poses'][label]['highest_vertices_max_shift']=float(np.linalg.norm(points[s][root]-base[s][root],axis=1).max())
 if label=='breath':assert set(changed)=={'Body_Reference'},changed
 if label.startswith('tail_'):assert set(changed)=={s},changed
 if label=='left_blink':assert set(changed)=={'Eye_L_White','Eye_L_UpperLid'},changed
 if label=='right_blink':assert set(changed)=={'Eye_R_White','Eye_R_UpperLid'},changed
 if label.startswith('sway_'):
  # A rotation must preserve every triangle edge length, including eyes/face.
  err=max(float(np.max(abs(np.linalg.norm(np.diff(points[s],axis=0),axis=1)-np.linalg.norm(np.diff(base[s],axis=0),axis=1)))) for s in ids)
  report['poses'][label]['max_edge_length_error_pixels']=err;assert err<.02,err
mouth=[]
for x in [0,.05,.1,.25,.5,.75,1]:
 im,points=capture({'ParamMouthOpenY':x});mouth.append((str(x),im))
 report.setdefault('mouth_cavity_height_pixels',[]).append(float(np.ptp(points['Mouth_Cavity'][:,1])))
assert np.all(np.diff(report['mouth_cavity_height_pixels'])>0)
# Full-size head crops, no redrawn or composited character.
def sheet(items,cols,size,crop,name):
 w,h=size;canvas=Image.new('RGB',(cols*w,math.ceil(len(items)/cols)*h),'#dce1ea');d=ImageDraw.Draw(canvas)
 for i,(label,im) in enumerate(items):
  tile=im.crop(crop);tile.thumbnail((w,h-28));x=i%cols*w+(w-tile.width)//2;y=i//cols*h+28;canvas.paste(tile,(x,y),tile);d.text((i%cols*w+10,i//cols*h+8),label,fill='#263245')
 canvas.save(out/name,quality=94)
sheet([(s,images[s]) for s in ['neutral','blink','half_blink','mouth_open']],4,(320,340),(180,205,600,620),'face-poses.jpg')
sheet(list(images.items()),4,(300,330),(0,0,768,768),'all-poses.jpg')
sheet(mouth,7,(170,110),(330,385,435,435),'mouth-steps.jpg')
report['passed']=True;(out/'dynamics-report.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
if '--animate' in sys.argv:
 frames=[]
 for i in range(180):
  t=i/30;blink=max(max(0,1-abs(t-at)/.13) for at in [1.2,4.4])
  pose={'ParamBodyAngleZ':5*math.sin(t*math.pi/3),'ParamBreath':.5-.5*math.cos(t*math.pi/2),'ParamHairSide':.3*math.sin(t*math.pi/3-.6),'ParamHairBack':.3*math.sin(t*math.pi/3-.9),'ParamEyeLOpen':1-blink,'ParamEyeROpen':1-blink,'ParamMouthOpenY':(.15+.55*max(0,math.sin(t*math.pi*4))) if 2<t<3.8 else 0}
  im,_=capture(pose);im.thumbnail((576,576));bg=Image.new('RGB',im.size,'#dce1ea');bg.paste(im,(0,0),im);frames.append(bg)
 frames[0].save(out/'front-dynamics-preview.gif',save_all=True,append_images=frames[1:],duration=33,loop=0)
v.makeCurrent();v.model.DestroyRenderer();v.model=None;v.doneCurrent();v.close();live2d.dispose()
