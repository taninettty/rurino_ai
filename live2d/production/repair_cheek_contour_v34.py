"""Recover the cropped cheek contour from its own original skin reference.
No face warp: a narrow source-pixel strip and separate editable contour.
"""
import json
from pathlib import Path
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
from scipy.interpolate import PchipInterpolator
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer
from outline_hair_layers_v34 import ROOT,W,H,DX,FONT,pixels,paste_full,tiled,sha
SOURCE=ROOT/'rebuild_v3_4/turn_redraw/three_hair_finish/Rurino_Three_Hair_Repairs_v034.psd'
REFERENCE=ROOT/'rebuild_v3_4/turn_redraw/side_blink_refinement/left/layers/Context_Skin_Reference.png'
OUT=ROOT/'rebuild_v3_4/turn_redraw/cheek_contour_recovery'
OUT.mkdir(exist_ok=True);(OUT/'qa').mkdir(exist_ok=True);(OUT/'layers').mkdir(exist_ok=True)
psd=PSDImage.open(SOURCE);layers={l.name:l for l in pixels(psd)}
face=layers['FacePaint_AfterCheekRecovery_SOURCE'];old=np.array(paste_full(face.topil().convert('RGBA'),face.offset))
source=np.array(Image.open(REFERENCE).convert('RGBA'))
# Track the genuine dark stroke, rather than reuse the inward-cut ownership mask.
ys=np.arange(1040,1235);centres=[]
for y in ys:
 x=np.where(old[y,:,3]>127)[0].min()-DX
 xx=np.arange(x-19,x-1);lum=source[y,xx,:3].mean(1)
 weight=np.maximum(160-lum,0)**2
 assert weight.sum()>0
 centres.append(float(np.sum(xx*weight)/weight.sum()))
centres=cv2.GaussianBlur(np.array(centres)[:,None],(1,25),4)[:,0]
curve=[(float(x),float(y)) for x,y in zip(centres,ys)]
curve += [(843,1236),(847,1238),(852,1240),(858,1241),(863,1241),(870,1239),(881,1236),(897,1231)]
# Source coordinates. Outer antialias boundary stays within the original stroke.
b=(620,1035,925,1255);s=4
p=[((x-b[0])*s,(y-b[1])*s) for x,y in curve]
mask=Image.new('L',((b[2]-b[0])*s,(b[3]-b[1])*s));d=ImageDraw.Draw(mask)
d.polygon(p+[((925-b[0])*s,(1231-b[1])*s),((925-b[0])*s,(1040-b[1])*s)],fill=255)
d.line(p,fill=255,width=3*s,joint='curve')
a=np.array(mask.resize((b[2]-b[0],b[3]-b[1]),Image.Resampling.LANCZOS)).astype(float)/255
ref=source[b[1]:b[3],b[0]:b[2]].copy();oldcrop=old[b[1]:b[3],DX+b[0]:DX+b[2]]
y,x=np.indices(a.shape);y=y+b[1];x=x+b[0]
# Local band only; old interior pixels remain authoritative.
dist=cv2.distanceTransform((oldcrop[:,:,3]<240).astype('uint8'),cv2.DIST_L2,5)
a*=np.clip((20-dist)/3,0,1)*np.clip((y-1040)/12,0,1)*np.clip((907-x)/10,0,1)
# Limit recovery to missing/antialiased pixels and a 2px overlap underneath.
inside=cv2.distanceTransform((oldcrop[:,:,3]>127).astype('uint8'),cv2.DIST_L2,5)
a*=np.clip((3-inside)/2,0,1)
# Decompose the recovered source strip into colour and dark contour; same RGB
# yields the original combined alpha when the two layers are composited.
strength=np.clip((185-ref[:,:,:3].mean(2))/35,0,1)
ia=a*strength
sa=np.divide(a-ia,1-ia,out=np.zeros_like(a),where=ia<.99999)
images={}
for name,alpha in [('CheekEdge_Skin_Recovery',sa),('Ink_FaceContour',ia)]:
 rgba=ref.copy();rgba[:,:,3]=np.rint(alpha*255).astype('uint8');rgba[rgba[:,:,3]==0]=0
 im=Image.fromarray(rgba);images[name]=im
 paste_full(im,(DX+b[0],b[1])).save(OUT/'layers'/(name+'.png'))
# Insert beneath the existing face; other geometry and every original layer remain.
parent=face.parent;index=parent.index(face)
for name in ['CheekEdge_Skin_Recovery','Ink_FaceContour']:
 layer=PixelLayer.frompil(images[name],psd_file=psd,layer_name=name,top=b[1],left=DX+b[0]);parent.insert(index,layer);index+=1
path=OUT/'Rurino_Cheek_Contour_Recovered_v034.psd'
assembled=tiled(psd)
psd._update_record();psd._record.image_data.set_data([c.tobytes() for c in assembled.split()],psd._record.header)
with path.open('wb') as f:psd._record.write(f)
# A small PSD can be imported as additional layers without remapping hair art.
addon=PSDImage.new('RGBA',(W,H),color=0)
for name in images:
 layer=PixelLayer.frompil(images[name],psd_file=addon,layer_name=name,top=b[1],left=DX+b[0]);addon.append(layer)
addon._update_record()
addview=Image.new('RGBA',(W,H))
for im in images.values():addview.alpha_composite(im,(DX+b[0],b[1]))
addon._record.image_data.set_data([c.tobytes() for c in addview.split()],addon._record.header)
with (OUT/'Rurino_Cheek_Contour_ADDON_v034.psd').open('wb') as f:addon._record.write(f)
print('saved PSDs',flush=True)
reopened=PSDImage.open(path);newlayers={l.name:l for l in pixels(reopened)}
for name,l in layers.items():
 n=newlayers[name];assert n.offset==l.offset and np.array_equal(np.array(n.topil()),np.array(l.topil())),name
assembled.save(OUT/'qa/cheek-recovered-assembled.png')
before=Image.open(ROOT/'rebuild_v3_4/turn_redraw/three_hair_finish/qa/three-repairs-assembled-Open.png')
crop=(1254,880,2004,1340);sheet=Image.new('RGB',(1530,510),'#e8edf3');draw=ImageDraw.Draw(sheet);font=ImageFont.truetype(FONT,24)
for i,(label,im) in enumerate([('修改前：脸颊黑线缺失',before),('修改后：恢复原图轮廓',assembled)]):
 c=im.crop(crop);sheet.paste(c,(i*765,45),c);draw.text((i*765+15,8),label,font=font,fill='#253342')
sheet.save(OUT/'qa/cheek-before-after.jpg',quality=97)
assembled.crop((DX+280,45,DX+1740,1400)).resize((876,813),Image.Resampling.LANCZOS).save(OUT/'qa/cheek-recovered-head.png')
report={'source_psd':str(SOURCE),'reference':str(REFERENCE),'output_sha256':sha(path),'original_pixel_layers_preserved':len(layers),'pixel_layers':len(newlayers),'added_layers':list(images),'note':'Recovered native cheek stroke and skin edge from original source. No face warp or changes to hair.'}
(OUT/'qa/recovery-report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report))
