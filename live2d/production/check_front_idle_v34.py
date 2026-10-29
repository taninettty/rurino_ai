"""Test the packaged idle/physics in the Cubism SDK and render continuous playback."""
import json,sys,math,subprocess
from pathlib import Path
import numpy as np
from PIL import Image
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage,QSurfaceFormat
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication,QOpenGLWidget
import live2d
path=Path(sys.argv[1]).resolve();out=path.parent.parent/'qa-dynamics'
QApplication.setAttribute(Qt.AA_ShareOpenGLContexts);fmt=QSurfaceFormat();fmt.setAlphaBufferSize(8);fmt.setVersion(2,1);QSurfaceFormat.setDefaultFormat(fmt);app=QApplication([]);live2d.init()
class View(QOpenGLWidget):
 def __init__(self):super().__init__();self.model=None;self.resize(576,576)
 def initializeGL(self):
  live2d.glInit();self.model=live2d.Model();self.model.LoadModelJson(str(path));self.model.SetAutoBlink(True);self.model.SetAutoBreath(True)
 def resizeGL(self,w,h):
  if self.model:self.model.Resize(w,h)
 def paintGL(self):
  if self.model:live2d.clearBuffer(0,0,0,0);self.model.Draw()
v=View();v.show();QTest.qWait(300);m=v.model;m.StartRandomMotion('Idle',1)
params=['ParamBodyAngleZ','ParamHairSide','ParamHairBack','ParamBreath','ParamEyeLOpen','ParamEyeROpen'];samples=[];frames=[];starts=1
for i in range(600):
 t=i/30;m.Update(1/30)
 if m.IsMotionFinished():m.StartRandomMotion('Idle',1);starts+=1
 # Only the middle 2 seconds demonstrate the mouth binding, with a synthetic envelope.
 m.SetParamById('ParamMouthOpenY',.15+.5*max(0,math.sin(t*math.pi*4)) if 5<t<7 else 0)
 samples.append([m.GetParamValueById(s) for s in params])
 if i<360:
  q=v.grabFramebuffer().convertToFormat(QImage.Format_RGBA8888);bits=q.bits();bits.setsize(q.byteCount());im=Image.frombytes('RGBA',(q.width(),q.height()),bytes(bits));bg=Image.new('RGB',im.size,'#dce1ea');bg.paste(im,(0,0),im);frames.append(bg)
s=np.array(samples);assert np.isfinite(s).all();assert s[:,0].min()<-4.9 and s[:,0].max()>4.9;assert np.ptp(s[480:,0])>3
assert (np.ptp(s[:,1:3],axis=0)>.05).all();assert (np.abs(s[:,1:3]).max(0)<.5).all();assert np.ptp(s[:,3])>.45;assert (s[:,4:6].min(0)<.1).all() and (s[:,4:6].max(0)>.99).all()
r={'passed':True,'seconds_tested':20,'preview_seconds':12,'restart_policy':'StartRandomMotion Idle when IsMotionFinished','playback_starts':starts,'parameter_ranges':{p:[float(s[:,i].min()),float(s[:,i].max())] for i,p in enumerate(params)},'preview_source':'actual Cubism SDK playing packaged idle, physics, authored idle blink and automatic breath; synthetic mouth envelope at 5-7 seconds, no audio','not_tested':['Windows hardware','voice service','Ollama service']};(out/'idle-runtime-report.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
ffmpeg=Path(sys.argv[2]).resolve()
proc=subprocess.Popen([str(ffmpeg),'-v','error','-y','-f','rawvideo','-pix_fmt','rgb24','-s','576x576','-r','30','-i','-','-an','-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-movflags','+faststart',str(out/'front-live2d-preview.mp4')],stdin=subprocess.PIPE)
for im in frames:proc.stdin.write(im.tobytes())
proc.stdin.close();assert proc.wait()==0
# A compact, shared-palette GIF avoids 26 MB of per-frame palettes.
thumbs=[im.resize((400,400),Image.Resampling.LANCZOS) for im in frames[::2]];palette=thumbs[0].quantize(colors=128);thumbs=[im.quantize(palette=palette,dither=Image.Dither.NONE) for im in thumbs];thumbs[0].save(out/'front-live2d-preview.gif',save_all=True,append_images=thumbs[1:],duration=[67,67,66]*60,loop=0,optimize=False)
v.makeCurrent();m.DestroyRenderer();v.model=None;v.doneCurrent();v.close();live2d.dispose()
