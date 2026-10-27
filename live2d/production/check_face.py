"""Render actual exported Cubism model at controlled parameter poses for visual QA."""
import json, sys, math
from pathlib import Path
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QSurfaceFormat, QImage
from PyQt5.QtWidgets import QApplication, QOpenGLWidget
from PyQt5.QtTest import QTest
from PIL import Image, ImageDraw
import live2d

path=Path(sys.argv[1]).resolve(); out=path.parent.parent/'qa';out.mkdir(exist_ok=True)
QApplication.setAttribute(Qt.AA_ShareOpenGLContexts)
fmt=QSurfaceFormat();fmt.setAlphaBufferSize(8);fmt.setVersion(2,1);QSurfaceFormat.setDefaultFormat(fmt)
app=QApplication([]);live2d.init()
class View(QOpenGLWidget):
 def __init__(self):
  super().__init__();self.pose={};self.model=None;self.resize(768,1024)
 def initializeGL(self):
  live2d.glInit();self.model=live2d.Model();self.model.LoadModelJson(str(path));self.model.SetAutoBlink(False);self.model.SetAutoBreath(False)
 def resizeGL(self,w,h):
  if self.model:self.model.Resize(w,h)
 def paintGL(self):
  if not self.model:return
  live2d.clearBuffer(0,0,0,0)
  self.model.ResetAllParameters()
  for k,v in self.pose.items():self.model.SetParamById(k,v)
  self.model.SaveParameters();self.model.Update(0);self.model.Draw()
v=View();v.show();QTest.qWait(1200)
assert v.model and v.model.GetParamCount()
ids=v.model.GetParamIds();standard='ParamAngleX' in ids
def p(old,new):return new if standard else old
ax=p('PARAM_ANGLE_X','ParamAngleX');ay=p('PARAM_ANGLE_Y','ParamAngleY');az=p('PARAM_ANGLE_Z','ParamAngleZ')
el=p('PARAM_EYE_L_OPEN','ParamEyeLOpen');er=p('PARAM_EYE_R_OPEN','ParamEyeROpen');mouth=p('PARAM_MOUTH_OPEN_Y','ParamMouthOpenY')
poses={f'face_x{x}_y{y}':{ax:x,ay:y} for y in [-30,-15,0,15,30] for x in [-30,-15,0,15,30]}
parameters=[{'id':s,'min':v.model.GetParamMinByIndex(i),'max':v.model.GetParamMaxByIndex(i),'default':v.model.GetParamDefaultByIndex(i)} for i,s in enumerate(ids)]
(out/'parameters.json').write_text(json.dumps(parameters,indent=2))
vertices={}
for name,pose in poses.items():
 v.pose=pose;v.update();QTest.qWait(80);v.grabFramebuffer().save(str(out/(name+'.png')))
 vertices[name]={ident:v.model.GetDrawableVertices(i) for i,ident in enumerate(v.model.GetDrawableIds()) if ident in ['D_FACE_00','D_NECK_00','D_NOSE_00','D_MOUTH_00','D_EYE_00','D_EYE_01']}
(out/'face-vertices.json').write_text(json.dumps(vertices))
ims=[]
for name in poses:
 im=Image.open(out/(name+'.png')).convert('RGBA');assert im.getchannel('A').getbbox(),name
 im=im.crop((275,150,490,335));im=im.resize((300,258),Image.Resampling.LANCZOS)
 tile=Image.new('RGB',(310,290),'#d5dae3');tile.paste(im,(5,25),im);ImageDraw.Draw(tile).text((8,7),name,fill='black');ims.append(tile)
sheet=Image.new('RGB',(1550,1450),'white')
for i,im in enumerate(ims):sheet.paste(im,(i%5*310,i//5*290))
sheet.save(out/'face-grid.jpg')
if '--animate' in sys.argv:
 frames=[]
 for frame in range(96):
  t=frame/24
  blink=max(0.,1-abs(t-1.5)/.12)
  v.pose={ax:20*math.sin(t*math.pi/2),ay:10*math.sin(t*math.pi),el:1-blink,er:1-blink,mouth:max(0,math.sin(t*math.pi*5))*.65 if 2<t<3.7 else 0}
  v.update();QTest.qWait(25)
  qimage=v.grabFramebuffer().convertToFormat(QImage.Format_RGBA8888)
  bits=qimage.bits();bits.setsize(qimage.byteCount())
  im=Image.frombytes('RGBA',(qimage.width(),qimage.height()),bytes(bits)).crop((160,10,610,570))
  im.thumbnail((360,448))
  bg=Image.new('RGB',im.size,'#d5dae3');bg.paste(im,(0,0),im)
  frames.append(bg)
 frames[0].save(out/'face-motion-preview.gif',save_all=True,append_images=frames[1:],duration=40,loop=0)
print(json.dumps({'parameters':len(ids),'drawables':len(v.model.GetDrawableIds()),'standard_ids':standard,'output':str(out)}))
v.makeCurrent();v.model.DestroyRenderer();v.model=None;v.doneCurrent();v.close();live2d.dispose()
