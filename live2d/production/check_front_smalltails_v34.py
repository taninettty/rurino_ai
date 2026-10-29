"""Verify hidden small-tail material is covered by actual exported triangles."""
import sys,json,hashlib
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QImage,QSurfaceFormat
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication,QOpenGLWidget
import live2d
base=Path(sys.argv[1]).resolve();path=base/'runtime/Rurino_Front_SmallTails_v034.model3.json';out=base/'qa-runtime'
QApplication.setAttribute(Qt.AA_ShareOpenGLContexts);fmt=QSurfaceFormat();fmt.setAlphaBufferSize(8);fmt.setVersion(2,1);QSurfaceFormat.setDefaultFormat(fmt)
app=QApplication([]);live2d.init()
class View(QOpenGLWidget):
 def __init__(self):super().__init__();self.model=None;self.resize(1024,1024)
 def initializeGL(self):
  live2d.glInit();self.model=live2d.Model();self.model.LoadModelJson(str(path));self.model.SetAutoBlink(False);self.model.SetAutoBreath(False)
 def resizeGL(self,w,h):
  if self.model:self.model.Resize(w,h)
 def paintGL(self):
  if self.model:
   live2d.clearBuffer(0,0,0,0);self.model.ResetAllParameters();self.model.Update(0);self.model.Draw()
v=View();v.show();QTest.qWait(600);v.grabFramebuffer();ids=v.model.GetDrawableIds();records=[];sheet=Image.new('RGB',(1200,680),'#e1e7ef');d=ImageDraw.Draw(sheet)
for j,n in enumerate(['SideHair_L','SideHair_R']):
 i=ids.index(n);verts=np.array(v.model.GetDrawableVertices(i)).reshape(-1,2);tri=np.array(v.model.GetDrawableIndices(i)).reshape(-1,3)
 coords=np.column_stack(((verts[:,0]+.5)*2048,(.5-verts[:,1])*2048));cover=np.zeros((2048,2048),np.uint8)
 for t in tri:cv2.fillConvexPoly(cover,np.rint(coords[t]).astype('int32'),255)
 a=np.array(Image.open(base/'colour'/f'{n}.png'));inside=cv2.erode((a[:,:,3]>220).astype('uint8'),np.ones((5,5),np.uint8))>0;missing=inside&(cover==0)
 rec={'id':n,'vertices':len(verts),'triangles':len(tri),'interior_pixels':int(inside.sum()),'interior_pixels_without_triangles':int(missing.sum()),'fraction_without_triangles':float(missing.sum()/inside.sum())};records.append(rec)
 # Include the standalone source and actual exported mesh overlay for inspection.
 ink=np.array(Image.open(base/'ink'/f'Ink_{n}.png'));inkcover=np.zeros_like(cover);ii=ids.index('Ink_'+n);iv=np.array(v.model.GetDrawableVertices(ii)).reshape(-1,2);it=np.array(v.model.GetDrawableIndices(ii)).reshape(-1,3);ic=np.column_stack(((iv[:,0]+.5)*2048,(.5-iv[:,1])*2048))
 for t in it:cv2.fillConvexPoly(inkcover,np.rint(ic[t]).astype('int32'),255)
 rec['ink_visible_pixels_without_triangles']=int(((ink[:,:,3]>60)&(inkcover==0)).sum())
 im=Image.alpha_composite(Image.fromarray(a),Image.fromarray(ink));overlay=Image.new('RGBA',im.size);draw=ImageDraw.Draw(overlay)
 for t in tri:draw.line([tuple(coords[x]) for x in list(t)+[t[0]]],fill=(22,121,90,95),width=1)
 im=Image.alpha_composite(im,overlay);box=Image.fromarray(a).getbbox();im=im.crop((box[0]-5,box[1]-5,box[2]+5,box[3]+5));im.thumbnail((560,610));sheet.paste(im,(j*600+(600-im.width)//2,50),im);d.text((j*600+20,15),n+' / exported triangles over material',fill='#263545')
 assert rec['fraction_without_triangles']<.001,rec
 distance=cv2.distanceTransform((inkcover==0).astype('uint8'),cv2.DIST_L2,5);print(n, 'ink max distance outside mesh',float(distance[ink[:,:,3]>60].max()),flush=True)
 assert rec['ink_visible_pixels_without_triangles']==0,rec
sheet.save(out/'smalltail-mesh-coverage.jpg',quality=96)
report={'passed':True,'scope':'static mesh coverage of completed hidden material; no motion or physics test','checks':records,'moc3_sha256':hashlib.sha256((path.parent/'Rurino_Front_SmallTails_v034.moc3').read_bytes()).hexdigest()};(out/'smalltail-mesh-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
v.makeCurrent();v.model.DestroyRenderer();v.model=None;v.doneCurrent();v.close();live2d.dispose()
