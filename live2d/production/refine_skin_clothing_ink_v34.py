"""Unify visible jaw, neck and clothing contours as separate editable dark ink.
Keeps anatomy and colour fields; cleans old dark rim pixels on the neck only.
"""
import gc,json
from pathlib import Path
import cv2,numpy as np
from scipy.ndimage import binary_fill_holes,distance_transform_edt
from scipy.interpolate import UnivariateSpline
from PIL import Image,ImageDraw,ImageFont
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer
from outline_hair_layers_v34 import ROOT,DX,W,H,FONT,pixels,paste_full,tiled,sha
SOURCE=ROOT/'rebuild_v3_4/turn_redraw/cheek_contour_recovery/Rurino_Cheek_Contour_Recovered_v034.psd'
OUT=ROOT/'rebuild_v3_4/turn_redraw/skin_clothing_ink';OUT.mkdir(exist_ok=True)
for n in ['layers','qa']:(OUT/n).mkdir(exist_ok=True)
psd=PSDImage.open(SOURCE);old={l.name:l for l in pixels(psd)};changes={};added={}
def full(l):return paste_full(l.topil().convert('RGBA'),l.offset)
def stroke(size,curves,width=3.1):
 scale=4;im=Image.new('L',(size[0]*scale,size[1]*scale));d=ImageDraw.Draw(im)
 for pts in curves:
  d.line([(round(x*scale),round(y*scale)) for x,y in pts],fill=235,width=round(width*scale),joint='curve')
 return np.array(im.resize(size,Image.Resampling.LANCZOS))
def smooth(points,axis=0,tolerance=1.0):
 a=np.asarray(points,float);v=a[:,axis];w=a[:,1-axis]
 fit=UnivariateSpline(v,w,s=len(v)*tolerance,k=3)
 v=np.linspace(v[0],v[-1],max(2,int((v[-1]-v[0])*3)))
 return np.column_stack([v,fit(v)]) if axis==0 else np.column_stack([fit(v),v])
def local(points,offset):return [(x+DX-offset[0],y-offset[1]) for x,y in points]
def bezier(points):
 a,b,c,d=map(np.array,points);t=np.linspace(0,1,300)[:,None]
 return (1-t)**3*a+3*(1-t)**2*t*b+3*(1-t)*t*t*c+t**3*d
def ink_rgba(alpha):
 a=np.zeros((*alpha.shape,4),np.uint8);a[:,:,3]=alpha;return Image.fromarray(a)
def insert(name,im,offset,after):
 box=im.getbbox();im=im.crop(box);offset=(offset[0]+box[0],offset[1]+box[1])
 parent=after.parent;index=parent.index(after)+1
 layer=PixelLayer.frompil(im,psd_file=psd,layer_name=name,left=offset[0],top=offset[1]);parent.insert(index,layer)
 added[name]=(im,offset);paste_full(im,offset).save(OUT/'layers'/(name+'.png'));return layer
# Jaw mask includes the restored missing cheek strip, not the old inward cut.
b=(1260,980,1970,1270);face=full(old['FacePaint_AfterCheekRecovery_SOURCE']).crop(b)
for n in ['CheekEdge_Skin_Recovery','Ink_FaceContour']:
 face=Image.alpha_composite(face,full(old[n]).crop(b))
a=np.array(face)[:,:,3]
points=[]
for x in range(645,1210,2):
 col=a[:,x+DX-b[0]];ys=np.where(col>127)[0]
 if len(ys):points.append((x,float(ys.max()+b[1])))
curve=smooth(points,tolerance=1.8)
aa=stroke(face.size,[local(curve,(b[0],b[1]))],3.0)
insert('Ink_FaceJaw_Clean',ink_rgba(aa),(b[0],b[1]),old['FacePaint_AfterCheekRecovery_SOURCE'])
# Remove the narrow white cut fringe on the left cheek, not the facial highlights.
l=old['FacePaint_AfterCheekRecovery_SOURCE'];arr=np.array(l.topil().convert('RGBA'));alpha=arr[:,:,3]
depth=cv2.distanceTransform((alpha>127).astype('uint8'),cv2.DIST_L2,5)
y,x=np.indices(alpha.shape);y+=l.top;x+=l.left-DX
valid=(depth>12)&(alpha>250);nearest=distance_transform_edt(~valid,return_distances=False,return_indices=True)
fringe=(x<875)&(y>1050)&(y<1235)&(depth<6)&(arr[:,:,:3].min(2)>238)&(alpha>0)
fixed=arr.copy();fixed[fringe,:3]=arr[nearest[0][fringe],nearest[1][fringe],:3]
new=PixelLayer.frompil(Image.fromarray(fixed),psd_file=psd,layer_name=l.name,left=l.left,top=l.top);l.parent[l.parent.index(l)]=new;changes[l.name]=Image.fromarray(fixed)
# The recovered strip uses the same adjacent face colour for its white rim.
r=old['CheekEdge_Skin_Recovery'];ra=np.array(r.topil().convert('RGBA'));ry,rx=np.indices(ra.shape[:2]);fy=np.clip(ry+r.top-l.top,0,arr.shape[0]-1);fx=np.clip(rx+r.left-l.left,0,arr.shape[1]-1)
fringe=(ra[:,:,3]>0)&(ra[:,:,:3].min(2)>238)
ra[fringe,:3]=arr[nearest[0][fy,fx][fringe],nearest[1][fy,fx][fringe],:3]
newr=PixelLayer.frompil(Image.fromarray(ra),psd_file=psd,layer_name=r.name,left=r.left,top=r.top);r.parent[r.parent.index(r)]=newr;changes[r.name]=Image.fromarray(ra)
# Neck: remove dark legacy rim colour, preserving the broad cast shadow and skin.
l=old['Neck_Visible'];arr=np.array(l.topil().convert('RGBA'));alpha=arr[:,:,3];depth=cv2.distanceTransform((alpha>127).astype('uint8'),cv2.DIST_L2,5)
y,x=np.indices(alpha.shape);y+=l.top;x+=l.left-DX
sidegate=(((x<940)&(y>1240))|((x>1115)&(y>1238)))&(y<1390)
oldline=(depth<10)&(alpha>0)&(arr[:,:,:3].mean(2)<185)&sidegate
valid=(depth>10)&(alpha>250)&(arr[:,:,:3].mean(2)>165)
nearest=distance_transform_edt(~valid,return_distances=False,return_indices=True)
fixed=arr.copy();fixed[oldline,:3]=arr[nearest[0][oldline],nearest[1][oldline],:3]
new=PixelLayer.frompil(Image.fromarray(fixed),psd_file=psd,layer_name=l.name,left=l.left,top=l.top);parent=l.parent;parent[parent.index(l)]=new;changes[l.name]=Image.fromarray(fixed)
curves=[]
for side in ['left','right']:
 points=[]
 for yy in range(1245,1537,2):
  xs=np.where(alpha[yy-l.top]>127)[0]
  if len(xs):points.append((float((xs.min() if side=='left' else xs.max())+l.left-DX),yy))
 curves.append(local(smooth(points,axis=1,tolerance=1.3),l.offset))
# The upper edge of the burgundy inset is a garment seam, not a thick skin outline.
points=[]
for xx in range(877,1175,2):
 ys=np.where(alpha[:,xx+DX-l.left]>127)[0]
 if len(ys):points.append((xx,float(ys.max()+l.top)))
curves.append(local(smooth(points,tolerance=.5),l.offset))
aa=stroke((arr.shape[1],arr.shape[0]),curves,2.8)
insert('Ink_Neck_Clean',ink_rgba(aa),l.offset,new)
# Clothing: outer silhouette and the white sailor collar have different
# widths; decorative gold stripes and broad cloth shadows remain untouched.
l=old['Body_Visible'];arr=np.array(l.topil().convert('RGBA'));alpha=arr[:,:,3];rgb=arr[:,:,:3].astype(float)
y,x=np.indices(alpha.shape);y+=l.top;x+=l.left-DX
curves=[]
# Free shoulders and sleeves: trace the actual silhouette as smooth curves.
for side in ['left','right']:
 points=[]
 for yy in range(1478,2044,2):
  xs=np.where(alpha[yy-l.top]>127)[0]
  points.append((float((xs.min() if side=='left' else xs.max())+l.left-DX),yy))
 curves.append(local(smooth(points,axis=1,tolerance=3.0),l.offset))
# Collar upper rim: follow the source curve; skip the cut occupied by foreground hair.
for start,end in [(475,895),(1160,1575)]:
 points=[]
 for xx in range(start,end,2):
  if 1410<xx<1540:continue
  ys=np.where(alpha[:,xx+DX-l.left]>127)[0]
  if len(ys):points.append((xx,float(ys.min()+l.top)))
 curves.append(local(smooth(points,tolerance=3.0),l.offset))
# Inner collar edges continue the neck contact down to the central V.
white=(rgb.min(2)>70)&((rgb.max(2)-rgb.min(2))<53)&(alpha>127)
white &= (x>470) & ((y<1750)|(x>600)) & (x<np.minimum(1590,1620-.6*(y-1500)))
# Spatial gates reject shirt fringes; disconnected collar tips remain included.
for side in ['left','right']:
 points=[]
 for yy in range(1538,1886,2):
  lo,hi=(780,1014) if side=='left' else (1015,1280)
  xs=np.where(white[yy-l.top,lo+DX-l.left:hi+DX-l.left])[0]+lo
  if len(xs):points.append((float(xs.max() if side=='left' else xs.min()),yy))
 curves.append(local(smooth(points,axis=1,tolerance=1.2),l.offset))
# Trace the actual outer collar, ignoring the occluded right segment where
# the thin foreground strand cuts through the old material.
for side in ['left','right']:
 points=[]
 for yy in range(1500 if side=='left' else 1448,1944,2):
  xs=np.where(white[yy-l.top])[0]+l.left-DX
  xs=xs[xs<1014] if side=='left' else xs[xs>1015]
  if not len(xs):continue
  if side=='right' and 1520<yy<1690:continue
  points.append((float(xs.min() if side=='left' else xs.max()),yy))
 curves.append(local(smooth(points,axis=1,tolerance=5.0),l.offset))
 if side=='left':curves.append(local(bezier([(475,1444),(469,1460),(475,1480),points[0]]),l.offset))
curves.append(local(bezier([(1014,1894),(1016,1911),(1014,1931),(1014,1943)]),l.offset))
ink=stroke((arr.shape[1],arr.shape[0]),curves,3.1)
# No construction line along the waist cut. Hair covers the inferred hidden
# portions of the collar curves; there is no box cut around the ink.
insert('Ink_Clothing_Clean',ink_rgba(ink),l.offset,l)
# Dark legacy line under the new jaw ink stays available as source recovery;
# it is no longer used to define the visible outline's colour or thickness.
for name,im in changes.items():paste_full(im,old[name].offset).save(OUT/'layers'/(name+'.png'))
print('Rendering corrected materials',flush=True)
assembled=tiled(psd);assembled.save(OUT/'qa/skin-clothing-assembled.png')
psd._update_record();psd._record.image_data.set_data([c.tobytes() for c in assembled.split()],psd._record.header)
path=OUT/'Rurino_Skin_Clothing_Ink_v034.psd'
with path.open('wb') as f:psd._record.write(f)
# Preserve exact existing layer attributes and pixels outside the narrow neck edit.
saved=PSDImage.open(path);layers={l.name:l for l in pixels(saved)};preserved=[]
for n,l in old.items():
 q=layers[n];assert l.offset==q.offset and (l.visible,l.opacity,l.blend_mode)==(q.visible,q.opacity,q.blend_mode)
 if n not in changes:assert np.array_equal(np.array(l.topil()),np.array(q.topil())),n;preserved.append(n)
 else:assert np.array_equal(np.array(changes[n]),np.array(q.topil().convert('RGBA')))
# Read back the new strokes so damaged offsets or PNG-only fixes cannot pass.
for n,(im,offset) in added.items():assert layers[n].offset==offset and np.array_equal(np.array(layers[n].topil().convert('RGBA')),np.array(im))
before=Image.open(SOURCE.parent/'qa/cheek-recovered-assembled.png')
font=ImageFont.truetype(FONT,22)
for name,box,scale in [('jaw-neck',(1240,1000,2010,1510),1),('collar',(1120,1280,2340,1970),.75)]:
 w=int((box[2]-box[0])*scale);h=int((box[3]-box[1])*scale);sheet=Image.new('RGB',(w*2+30,h+55),'#e7eaf0');d=ImageDraw.Draw(sheet)
 for i,(lab,im) in enumerate([('修改前',before),('修改后',assembled)]):
  q=im.crop(box).resize((w,h),Image.Resampling.LANCZOS);bg=Image.new('RGBA',q.size,'#e7eaf0');bg.alpha_composite(q);sheet.paste(bg.convert('RGB'),(i*(w+15),45));d.text((i*(w+15)+10,10),lab+' · '+('脸颊与脖子' if name=='jaw-neck' else '衣领与衣服'),font=font,fill='#263344')
 sheet.save(OUT/'qa'/(name+'-before-after.jpg'),quality=97)
q=assembled.crop((DX+240,50,DX+1810,2048));q.thumbnail((900,1150));bg=Image.new('RGBA',q.size,'#e7eaf0');bg.alpha_composite(q);bg.convert('RGB').save(OUT/'qa/bust-preview.jpg',quality=96)
report={'source':str(SOURCE),'psd_sha256':sha(path),'preserved_layers':preserved,'modified_layers':list(changes),'added_layers':list(added),'pixel_layers':len(layers),'neck_legacy_rim_pixels_cleaned':int(oldline.sum()),'widths_source_px':{'jaw':3.0,'neck':2.8,'clothing':3.1},'scope':'visible contour cleanup, no new motion or anatomy deformation'}
(OUT/'qa/material-check.json').write_text(json.dumps(report,indent=2));print(json.dumps(report),flush=True)
