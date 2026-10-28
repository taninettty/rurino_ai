"""Separate eyebrow-overlap patches from the two crown/fringe source layers.
No new hair strand count: this removes a known ownership ambiguity before tracing.
"""
import json
import cv2
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from psd_tools import PSDImage
from split_head_v34 import mask
from split_left_head_parts_v34 import TURN,pixels,clone,add,sha
from build_hair_flow_redraw_v34 import full
SOURCE=TURN/'hair_structure_assembly/Rurino_Hair_Structure_Assembly_v034.psd'
OUT=TURN/'fringe_overlap_separation';FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
# Small closed patches follow the visible brow arcs in the 1024 reference.
# They include edge pixels and are not asserted to be complete isolated brows.
PATCHES={
 'L':('Bang_ImageLeft_Visible','M 264 347 C 289 324 318 308 337 313 Q 354 316 369 332 Q 342 318 323 324 Q 294 331 264 347 Z'),
 'R':('Bang_ImageRight_Visible','M 452 333 C 469 317 490 309 510 312 Q 558 316 608 350 Q 561 330 517 325 Q 480 317 452 333 Z'),
}
def panel(items,box,path):
 sheet=Image.new('RGB',(1440,len(items)*330),'#e8edf3');d=ImageDraw.Draw(sheet);font=ImageFont.truetype(FONT,21)
 for row,cols in enumerate(items):
  for col,(label,a) in enumerate(cols):
   x=col*480;y=row*330;d.text((x+10,y+10),label,font=font,fill='#26364a')
   for cy in range(y+45,y+320,16):
    for cx in range(x+10,x+470,16):d.rectangle((cx,cy,cx+15,cy+15),fill='#cbd5e1' if (cy//16+cx//16)%2 else '#e8edf3')
   im=Image.fromarray(a).crop(box[row]);scale=min(450/im.width,260/im.height);im=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.LANCZOS);sheet.paste(im,(x+(480-im.width)//2,y+52),im)
 sheet.save(path,quality=97)
def main():
 for f in ['layers','masks','qa']:(OUT/f).mkdir(parents=True,exist_ok=True)
 source=PSDImage.open(SOURCE);lookup={l.name:l for l in pixels(source)};parts={};records=[];rows=[]
 for side,(name,path) in PATCHES.items():
  a=full(lookup[name]);a[a[:,:,3]==0]=0;region=cv2.dilate(mask(path).astype('uint8'),np.ones((17,17),np.uint8))>0;hair=a.copy();hair[region]=0;brow=a.copy();brow[~region]=0
  assert np.array_equal(np.where(region[:,:,None],brow,hair),a)
  assert (brow[:,:,3]>0).any()
  parts[name]=[(f'CrownFringe_{side}_BrowPatchRemoved_SHARED',hair),(f'BrowOverlap_{side}_FromHair_PATCH_ONLY',brow)]
  for n,arr in parts[name]:Image.fromarray(arr).save(OUT/'layers'/(n+'.png'))
  Image.fromarray((region*255).astype('uint8')).save(OUT/'masks'/(side+'-brow-patch.png'))
  rows.append([(side+' · 原刘海层',a),(side+' · 覆盖区分出后',hair),(side+' · 单独眉线覆盖区',brow)])
  records.append({'side':side,'source_layer':name,'path_1024':path,'patch_padding_source_pixels':8,'moved_alpha_pixels':int((brow[:,:,3]>0).sum()),'scope':'brow-overlap patch from hair source only, includes adjacent antialias/background pixels; not complete brow artwork'})
 psd=PSDImage.new('RGBA',(2048,2048),color=0);clone(source,psd,psd,[]);dest={l.name:l for l in pixels(psd)}
 for name,items in parts.items():
  old=dest[name];parent=old.parent;index=list(parent).index(old)
  for n,arr in items:
   new=add(psd,parent,Image.fromarray(arr),n);parent.remove(new);parent.insert(index,new);index+=1
  old.visible=False
 path=OUT/'Rurino_Crown_Fringe_Overlap_Separated_v034.psd';psd.save(path);saved=PSDImage.open(path);after={l.name:l for l in pixels(saved)}
 for n,old in lookup.items():
  new=after[n];assert new.offset==old.offset and np.array_equal(np.array(new.topil()),np.array(old.topil())),n
  assert (old.opacity,old.blend_mode,old.clipping_layer)==(new.opacity,new.blend_mode,new.clipping_layer),n
  assert new.visible==(False if n in parts else old.visible),n
 for items in parts.values():
  for n,arr in items:assert np.array_equal(full(after[n]),arr),n
 states=[]
 for state in ['Open','Half','Closed']:
  for doc in [source,saved]:
   for g in doc:
    if g.name.startswith('02_'):g.visible=g.name=='02_'+state
  before=np.array(source.composite(force=True));actual=np.array(saved.composite(force=True));assert np.array_equal(before,actual),state
  states.append({'state':state,'whole_composite_rgba_exact':True})
  if state=='Open':Image.fromarray(actual).save(OUT/'qa/saved-psd-open.png')
 panel(rows,[(490,550,780,810),(880,550,1250,810)],OUT/'qa/brow-overlap-detail.jpg')
 # Full layer silhouettes are separate from close-up evidence.
 panel(rows,[(440,80,1010,820),(860,80,1320,820)],OUT/'qa/fringe-overlap-full-alpha.jpg')
 report={'input_sha256':sha(SOURCE),'saved_sha256':sha(path),'pixel_layers':len(after),'original_62_layers_retained':True,'parts':records,'states':states,'new_hair_strands':0,'crown_fringe_separation_completed':False,'limitations':['only eyebrow-overlap patches within the original bang layers were separated','patches include nearby edge/background pixels, not complete eyebrow layers','removed patches leave transparent gaps in isolated hair; under-brow hair reconstruction deferred','crown/fringe shared surface and internal strand identities are still pending','no repainting, mesh or physics'],'rejected_72_layer_candidate_used':False}
 (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
