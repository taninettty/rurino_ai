"""Individually trace the visible short-hair locks in the left-facing drawing.

Curves follow drawn lock borders, not equal-width strips. This stage retains a
separate unrefined root/flower boundary and does not invent concealed hair.
"""
import json,hashlib
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from psd_tools import PSDImage
from psd_tools.api.layers import Group
from split_head_v34 import mask
from split_left_head_parts_v34 import ROOT,TURN,pixels,clone,add,sha
SOURCE=TURN/'left_head_parts/Rurino_Left_Head_Visible_Parts_v034.psd'
OUT=TURN/'left_hair_strands';FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
# Coordinates at 1024; masks rasterized at the original 2048 resolution.
# ImageLeft/ImageRight always means viewer left/right, not the character's.
TRACES={
'ShortRearHair_ImageRight':[
 ('R01_OuterFlick','右 01 · 外翘束', 'M 817 221 Q 846 248 857 278 Q 870 315 875 359 Q 910 391 952 385 L 974 376 L 974 286 L 871 200 Z', (943,382)),
 ('R02_OuterDrop','右 02 · 外垂束', 'M 804 233 Q 842 250 857 278 Q 870 317 875 357 Q 893 410 879 451 Q 870 472 860 487 Q 867 458 852 427 Q 839 396 835 365 Q 837 310 815 267 Z', (861,482)),
 ('R03_UnderDrop','右 03 · 后侧尖束露出段', 'M 834 367 Q 840 390 853 426 Q 855 470 789 505 Q 821 469 830 432 Q 840 397 834 367 Z', (793,499)),
 ('R04_MainDrop','右 04 · 长垂束', 'M 773 248 Q 804 248 818 281 Q 839 329 837 376 Q 838 422 809 467 Q 785 494 748 516 Q 774 482 775 429 Q 804 401 794 365 Q 788 302 773 248 Z', (750,511)),
 ('R05_InnerLock','右 05 · 内侧遮挡束', 'M 744 245 Q 773 253 779 296 Q 791 329 796 366 Q 806 402 777 429 Q 749 454 707 469 L 690 443 L 679 432 L 690 311 Z', (718,459)),
],
'ShortRearHair_ImageLeft':[
 ('L01_OuterFlick','左 01 · 外翘束', 'M 206 245 Q 187 278 180 308 Q 170 338 166 363 Q 140 388 103 390 L 88 383 L 89 298 L 194 233 Z', (106,384)),
 ('L02_OuterDrop','左 02 · 外垂束', 'M 211 249 Q 194 279 184 309 Q 175 337 166 361 Q 153 403 159 443 Q 164 469 183 485 Q 176 459 181 431 Q 195 391 203 349 Q 205 295 221 254 Z', (181,479)),
 ('L03_MiddleDrop','左 03 · 中间垂束露出段', 'M 202 361 Q 199 407 216 436 Q 216 466 224 493 Q 188 476 181 432 Q 190 398 202 361 Z', (218,485)),
]}


def full(l):
 im=Image.new('RGBA',(2048,2048));im.paste(l.topil().convert('RGBA'),l.offset);return np.array(im)
def dump(p,data):p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
def location_map(neutral,records):
 # Numbered map shows source-space positions and true source size relations.
 panel=Image.new('RGBA',neutral.size,'#e8edf4');panel.alpha_composite(neutral);panel=panel.resize((1024,1024));draw=ImageDraw.Draw(panel);f=ImageFont.truetype(FONT,18)
 for r in records:
  x,y=r['visible_tip_xy_1024'];right=r['name'].startswith('R');endx=970 if right else 52;endy={'R01':345,'R05':432,'R02':477,'R03':520,'R04':562,'L01':340,'L02':460,'L03':510}[r['name'][:3]]
  draw.line((x,y,endx,endy),fill='#a12e64',width=2);draw.ellipse((x-3,y-3,x+3,y+3),fill='#a12e64');draw.text((endx-18,endy-23),r['name'][:3],font=f,fill='#692047')
 panel.convert('RGB').save(OUT/'qa/lock-location-map.jpg',quality=96)

def main():
 for folder in ['layers','masks','qa']:(OUT/folder).mkdir(parents=True,exist_ok=True)
 # Remove only the superseded candidate produced by this builder revision.
 for relative in ['layers/L04_InnerLock.png','masks/L04_InnerLock.png']:
  obsolete=OUT/relative
  if obsolete.exists():obsolete.unlink()
 source=PSDImage.open(SOURCE);lookup={l.name:l for l in pixels(source)};splits={};records=[]
 for parent,paths in TRACES.items():
  original=full(lookup[parent]);valid=original[:,:,3]>0;claimed=np.zeros(valid.shape,bool);parts={};recon=np.zeros_like(original)
  for name,label,path,tip in paths:
   region=mask(path)&~claimed
   # The old coarse parent included pink ponytail pixels below blue tips.
   # Retain those in the pending layer rather than carrying them with a lock.
   yy=np.indices(valid.shape)[0];rgb=original[:,:,:3].astype('int16')
   region&=~((yy>800)&(rgb[:,:,0]>rgb[:,:,2]+2))
   claimed|=region
   p=original.copy();p[~region]=0;assert p[:,:,3].any(),name
   parts[name]=Image.fromarray(p);recon[region]=p[region]
   parts[name].save(OUT/'layers'/f'{name}.png');Image.fromarray((region*255).astype('uint8')).save(OUT/'masks'/f'{name}.png')
   records.append({'name':name,'label':label,'parent':parent,'path':path,'visible_tip_xy_1024':list(tip),'visible_pixels':int((p[:,:,3]>0).sum()),'bbox':list(parts[name].getbbox()),'status':'visible lock only; concealed root and underlap incomplete'})
  p=original.copy();p[claimed]=0;name=parent+'_RootBoundary_PENDING';parts[name]=Image.fromarray(p);recon[~claimed]=p[~claimed]
  parts[name].save(OUT/'layers'/f'{name}.png');assert np.array_equal(recon,original)
  splits[parent]=parts
 psd=PSDImage.new('RGBA',(2048,2048),color=0);preserved=[]
 def rebuild(items,parent):
  for item in items:
   if item.name in splits:
    g=Group.new(item.name+'_IndividualVisibleLocks',parent=parent)
    for name,im in splits[item.name].items():add(psd,g,im,name)
   elif item.is_group():
    g=Group.new(item.name,parent=parent);g.visible=item.visible;g.opacity=item.opacity
    if item.blend_mode is not None:g.blend_mode=item.blend_mode
    rebuild(item,g)
   else:clone([item],parent,psd,preserved)
 rebuild(source,psd)
 path=OUT/'Rurino_Left_Head_Hair_Strands_v034.psd';psd.save(path)
 dump(OUT/'manifest.json',{'source_psd':str(SOURCE.relative_to(ROOT)),'source_sha256':sha(SOURCE),'saved_psd_sha256':sha(path),'canvas':[2048,2048],'traced_locks':records,'lock_count':len(records),'root_boundary_layers':[k+'_RootBoundary_PENDING' for k in TRACES],'preserved_layers':preserved,'pixel_layer_count':len(list(pixels(psd))),'original_parent_partition_exact':True,'scope':'eight visible short-hair locks; not finished rooted parts or physics','limitations':['upper roots and flower margins remain in explicit pending layers','hidden overlap extensions are not complete','brow-overlapping bangs and long ponytails not subdivided this stage','separation is not continuous motion validation']})
 sheet=Image.new('RGB',(1500,490*3),'#e8edf4');d=ImageDraw.Draw(sheet);font=ImageFont.truetype(FONT,22)
 for i,r in enumerate(records):
  im=splits[r['parent']][r['name']];box=im.getbbox();crop=im.crop(box);crop.thumbnail((470,435));x=i%3*500;y=i//3*490;sheet.paste(crop,(x+(500-crop.width)//2,y+42),crop);d.text((x+12,y+7),r['label'],font=font,fill='#25344a')
 d.multiline_text((1018,1030),'本轮：8 缕可见发束\n\n上端隐藏发根仍待补绘\n刘海、长马尾继续保留待拆\n各格单独放大，非实际大小比例',font=font,fill='#42536b',spacing=14)
 sheet.save(OUT/'qa/individual-locks.jpg',quality=96)
 location_map(source.composite(force=True),records)
 print(json.dumps({'pixel_layers':len(list(pixels(psd))),'visible_locks':len(records),'psd':str(path)},indent=2))
if __name__=='__main__':main()
