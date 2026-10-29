"""Compare pre/post cheek repair Cubism exports, geometry and rendered locality."""
import sys,json,hashlib
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QSurfaceFormat,QImage
from PyQt5.QtWidgets import QApplication,QOpenGLWidget
from PyQt5.QtTest import QTest
import live2d
oldpath,newpath=map(lambda p:Path(p).resolve(),sys.argv[1:3]);out=newpath.parent.parent/'qa-ink';out.mkdir(exist_ok=True)
QApplication.setAttribute(Qt.AA_ShareOpenGLContexts);fmt=QSurfaceFormat();fmt.setVersion(2,1);fmt.setAlphaBufferSize(8);QSurfaceFormat.setDefaultFormat(fmt)
app=QApplication([]);live2d.init()
class View(QOpenGLWidget):
 def __init__(self):super().__init__();self.models=[];self.index=0;self.pose=(0,0);self.resize(1600,1304)
 def initializeGL(self):
  live2d.glInit()
  for p in [oldpath,newpath]:
   m=live2d.Model();m.LoadModelJson(str(p));m.SetAutoBlink(False);m.SetAutoBreath(False);self.models.append(m)
 def resizeGL(self,w,h):
  for m in self.models:m.Resize(w,h)
 def paintGL(self):
  if not self.models:return
  m=self.models[self.index];live2d.clearBuffer(0,0,0,0);m.ResetAllParameters()
  for name,v in zip(['ParamHairSmallL','ParamHairSmallR'],self.pose):m.SetParamById(name,v)
  m.SaveParameters();m.Update(0);m.Draw()
v=View();v.show();QTest.qWait(600)
def capture(index,pose):
 v.index=index;v.pose=pose;v.update();QTest.qWait(80)
 q=v.grabFramebuffer().convertToFormat(QImage.Format_RGBA8888);bits=q.bits();bits.setsize(q.byteCount());im=Image.frombytes('RGBA',(q.width(),q.height()),bytes(bits))
 m=v.models[index];ids=m.GetDrawableIds()
 return im,{name:np.array(m.GetDrawableVertices(i)) for i,name in enumerate(ids)}
report={'before':oldpath.name,'after':newpath.name,'geometry_samples':[]}
for pose in [(0,0),(-1,1),(1,-1)]:
 a,old=capture(0,pose);b,new=capture(1,pose)
 added=set(new)-set(old);assert added=={'Ink_FaceJaw_Clean','Ink_Neck_Clean','Ink_Clothing_Clean'}
 errors={name:float(abs(old[name]-new[name]).max()) for name in old};assert max(errors.values())==0
 report['geometry_samples'].append({'pose':pose,'preserved_drawables':len(old),'max_vertex_error':0})
 if pose==(0,0):before,after=a,b
assert v.models[0].GetParamIds()==v.models[1].GetParamIds()
report['same_parameters']=True;report['added_drawables']=sorted(added)
# Compare composited pixels to avoid meaningless RGB differences at zero alpha.
def grey(im):
 bg=Image.new('RGBA',im.size,(231,234,240,255));return Image.alpha_composite(bg,im).convert('RGB')
a=np.array(grey(before));b=np.array(grey(after));delta=abs(a.astype(int)-b.astype(int)).max(2)
y,x=np.where(delta>3);report['changed_pixel_bbox_over_3_255']=[int(x.min()),int(y.min()),int(x.max()+1),int(y.max()+1)];report['changed_pixels_over_3_255']=int(len(x))
# The existing atlas may be repacked to accommodate three new editable inks.
# Outside the repaired regions, compare separately and report texture resampling.
allowed=np.zeros(delta.shape,bool);sx=1600/3456;sy=1304/2816
allowed[int(970*sy):int(2060*sy)+1,int(910*sx):int(2550*sx)+1]=True
report['outside_repair_pixels_over_3_255']=int(np.sum((delta>3)&~allowed))
report['outside_repair_mean_error']=float(delta[~allowed].mean())
assert report['outside_repair_mean_error']<2
before.save(out/'before.png');after.save(out/'after.png')
# Actual SDK render, displayed without resampling to preserve the thin line.
box=(425,450,1180,955);sheet=Image.new('RGB',(1540,555),'#e7eaf0');d=ImageDraw.Draw(sheet);font=ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',21)
for i,(label,im) in enumerate([('修改前 · 运行模型',before),('修改后 · 运行模型',after)]):
 sheet.paste(grey(im).crop(box),(i*770+8,43));d.text((i*770+10,10),label,font=font,fill='#253342')
sheet.save(out/'runtime-ink-before-after.jpg',quality=98)
grey(after).crop((400,0,1240,955)).save(out/'runtime-repaired-bust.png')
report['passed']=True;(out/'runtime-comparison.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
v.makeCurrent()
for m in v.models:m.DestroyRenderer()
v.models=[];v.doneCurrent();v.close();live2d.dispose()
