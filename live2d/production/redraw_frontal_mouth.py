"""Draw frontal mouth materials; preserve PSD identity for Cubism reimport.
Requires archived rebuild_v3 layers and the v0.3.1 PSD; not an automatic rig.
"""
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer
import json
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'rebuild_v3_2';OUT.mkdir(exist_ok=True)
SIZE=(1536,2048)
# Work in the approved 768x1024 coordinate system at 4x sampling.
scale=4;box=(345,250,423,305)
y,x=np.mgrid[250*scale:305*scale,345*scale:423*scale]/scale
cx=384
# Smooth symmetrical bowl, round lower contour, no copied reference pixels.
u=(x-cx)/16
arc=np.sqrt(np.maximum(0,1-u*u))
top=274-2.3*arc;bottom=274+16.5*arc
inside=(abs(u)<=1)&(y>=top)&(y<=bottom)
depth=np.clip((y-top)/(bottom-top+1e-4),0,1)
color=np.zeros((*x.shape,4),dtype=np.uint8)
for c,(dark,light) in enumerate([(107,224),(45,123),(57,133)]):
 color[:,:,c]=(dark+(light-dark)*np.sqrt(depth)).astype('uint8')
# A softly lit tongue centered at the base, without a side-facing highlight.
tongue=np.clip(1-((x-cx)/13)**2-((y-290)/6)**2,0,1)*.28
for c,target in enumerate([246,153,159]):color[:,:,c]=(color[:,:,c]*(1-tongue)+target*tongue).astype('uint8')
color[:,:,3]=inside*255
mouth=Image.new('RGBA',SIZE);mouth.alpha_composite(Image.fromarray(color).resize((156,110),Image.Resampling.LANCZOS),(690,500))
# The rebuilt neutral keyforms use the facial center directly.
shifted=Image.new('RGBA',SIZE);shifted.alpha_composite(mouth,(0,0))
replacements={'D_MOUTH_00':shifted}
face=Image.open(ROOT/'rebuild_v3/layers/Face_Base.png').convert('RGBA')
yy,xx=np.mgrid[:2048,:1536]/2
# Shared, symmetric edge. Small overlap avoids a seam at closure.
edge=275+2.2*np.maximum(0,1-((xx-cx)/16)**2)
outer=np.clip((xx-350)/3,0,1)*np.clip((418-xx)/3,0,1)
for key,upper in [('D_MOUTH_03',True),('D_MOUTH_01',False)]:
 alpha=outer*(np.clip((edge+.25-yy)*2,0,1)*np.clip((yy-250)/3,0,1) if upper else np.clip((yy-edge+.25)*2,0,1)*np.clip((300-yy)/5,0,1))
 # Bound the moving lower skin patch to the mouth neighbourhood, not the chin.
 if not upper:
  patch_u=(xx-cx)/18
  patch_bottom=274+19*np.sqrt(np.maximum(0,1-patch_u*patch_u))
  alpha*=np.clip((18-np.abs(xx-cx))*2,0,1)*np.clip((patch_bottom-yy)*2,0,1)
 a=np.array(face);a[:,:,3]=(alpha*255).astype('uint8');replacements[key]=Image.fromarray(a)
# Frontal short smile: level corners, center on the facial axis.
lip=Image.new('RGBA',(3072,4096));d=ImageDraw.Draw(lip)
pts=[((cx+v)*4,(275+2.2*(1-(v/16)**2))*4) for v in np.linspace(-14,14,150)]
d.line(pts,fill=(142,83,78,220),width=3)
replacements['D_MOUTH_03'].alpha_composite(lip.resize(SIZE,Image.Resampling.LANCZOS))
psd=PSDImage.open(ROOT/'rebuild_v3_1/Rurino_Face_Corrected_t032.psd')
for old in list(psd.descendants()):
 if old.is_group() or old.name not in replacements:continue
 im=replacements[old.name];bounds=im.getbbox()
 new=PixelLayer.frompil(im.crop(bounds),psd_file=psd,layer_name=old.name,top=bounds[1],left=bounds[0])
 new._record.tagged_blocks=old._record.tagged_blocks
 parent=old.parent;i=parent.index(old);parent.remove(old);parent.insert(i,new)
psd.save(OUT/'Rurino_Frontal_Mouth_t044.psd')
psd.composite(force=True).save(OUT/'material-neutral.png')
for key,im in replacements.items():im.save(OUT/(key+'.png'))
(OUT/'mouth-repair.json').write_text(json.dumps({'source':'new symmetric frontal mouth raster, no reused expression mouth pixels','layers':list(replacements),'review_center_x':cx,'mouth_half_width':16,'oral_mesh_material_offset_highres_px':0,'status':'requires Cubism reimport and render review'},indent=2))
print('Saved frontal mouth PSD')
