"""Split two observable right-fringe lower branches, keeping a shared remainder.
Observed contour and provisional root closure are explicitly distinguished.
"""
import json
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from psd_tools import PSDImage
from split_head_v34 import mask
from split_left_head_parts_v34 import TURN,pixels,clone,add,sha
from build_hair_flow_redraw_v34 import full
SOURCE=TURN/'fringe_overlap_separation/Rurino_Crown_Fringe_Overlap_Separated_v034.psd'
OUT=TURN/'right_fringe_visible_split';FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
SOURCE_LAYER='CrownFringe_R_BrowPatchRemoved_SHARED'
PATHS={
 'Fringe_R_C_VisibleLower':'M 483 202 Q 518 179 557 200 C 571 241 580 282 579 309 C 578 335 565 361 547 377 Q 552 366 548 356 C 538 335 511 294 492 260 C 490 247 486 225 483 202 Z',
 'Fringe_R_D_VisibleLower':'M 557 200 Q 576 192 590 230 C 601 262 610 306 599 339 Q 588 369 571 391 C 579 357 580 330 579 309 C 580 282 571 241 557 200 Z',
}
LABELS={'Fringe_R_C_VisibleLower':'C · 中间可见段','Fringe_R_D_VisibleLower':'D · 外侧可见段','CrownFringe_R_SharedRemainder_PENDING':'共用发面 / 其他区域 · 待定'}

def checker(size):
 im=Image.new('RGB',size,'#e8edf3');d=ImageDraw.Draw(im)
 for y in range(0,size[1],20):
  for x in range(0,size[0],20):
   if (x//20+y//20)%2:d.rectangle((x,y,x+19,y+19),fill='#cbd6e2')
 return im

def extract(a):
 a=a.copy();a[a[:,:,3]==0]=0;claimed=np.zeros((2048,2048),bool);parts={};records=[]
 for n,path in PATHS.items():
  region=mask(path)&~claimed;claimed|=region;b=a.copy();b[~region]=0;parts[n]=b
  records.append({'name':n,'path_1024':path,'visible_alpha_pixels':int((b[:,:,3]>0).sum()),'root_status':'top closure is a provisional construction seam, not an observed original boundary','brow_gap':'retained from prior stage; not repainted'})
 b=a.copy();b[claimed]=0;parts['CrownFringe_R_SharedRemainder_PENDING']=b
 recon=np.zeros_like(a)
 for arr in parts.values():
  hit=arr[:,:,3]>0;assert not (recon[:,:,3][hit]>0).any();recon[hit]=arr[hit]
 assert np.array_equal(recon,a)
 return parts,records

def previews(parts,source_layer,head):
 font=ImageFont.truetype(FONT,22);small=ImageFont.truetype(FONT,18)
 # Full layer alpha view, not a cropped composite presented as a strand.
 sheet=Image.new('RGB',(1440,900),'#edf1f6');d=ImageDraw.Draw(sheet)
 box=Image.fromarray(source_layer[:,:,3]).getbbox();box=(max(0,box[0]-12),max(0,box[1]-12),min(2048,box[2]+12),min(2048,box[3]+12))
 for i,(n,a) in enumerate(parts.items()):
  x=i*480;sheet.paste(checker((460,770)),(x+10,60));d.text((x+10,18),LABELS[n],font=font,fill='#26394c')
  im=Image.fromarray(a).crop(box);scale=min(440/im.width,740/im.height);im=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.LANCZOS);sheet.paste(im,(x+(480-im.width)//2,75),im)
 d.text((18,850),'实际独立图层；同一视口和比例。上端是临时构造切线，眉线缺口待最后补画。',font=small,fill='#52647a');sheet.save(OUT/'qa/right-fringe-full-alpha.jpg',quality=97)
 # Show the traced boundary in the source image. Root closure is dashed yellow.
 base=Image.new('RGBA',(2048,2048),'#dce5ef');base.alpha_composite(Image.fromarray(head));plain=base.copy()
 palette=[(225,64,113),(37,160,199)]
 import cv2
 for (n,a),colour in zip(list(parts.items())[:2],palette):
  region=mask(PATHS[n]).astype('uint8');edge=cv2.morphologyEx(region,cv2.MORPH_GRADIENT,np.ones((3,3),np.uint8))
  overlay=np.zeros((2048,2048,4),dtype='uint8');overlay[:,:,:3]=colour;overlay[:,:,3]=edge*255;base.alpha_composite(Image.fromarray(overlay))
 draw=ImageDraw.Draw(base)
 for pts in [((483,202),(518,179),(557,200)),((557,200),(576,192),(590,230))]:
  p0,p1,p2=[np.array(p)*2 for p in pts];xy=[]
  for t in np.linspace(0,1,80):xy.append(tuple((1-t)**2*p0+2*(1-t)*t*p1+t*t*p2))
  for i in range(0,len(xy)-1,6):draw.line(xy[i:i+3],fill='#f4b62e',width=5)
 guide=Image.new('RGB',(1420,920),'#edf1f6');gd=ImageDraw.Draw(guide)
 for i,(title,im) in enumerate([('原图 · 轮廓核对',plain),('轮廓候选 · 黄色虚线为临时根部切线',base)]):
  crop=im.crop((940,350,1250,810)).resize((465,690));guide.paste(crop,(i*690+110,100),crop);gd.text((i*690+20,30),title,font=font,fill='#26394c')
 gd.text((25,825),'粉色 C：中间段；蓝色 D：外侧段。只拆可见下段，不将临时上边界当作真实发根。',font=small,fill='#52647a')
 gd.text((25,865),'原图中上方轮廓逐渐消失，共用区保留待定。所有缺失像素与眉线覆盖区仍按来源保留。',font=small,fill='#52647a');guide.save(OUT/'qa/right-fringe-contour-review.jpg',quality=97)

def main():
 for f in ['layers','masks','qa']:(OUT/f).mkdir(parents=True,exist_ok=True)
 source=PSDImage.open(SOURCE);lookup={l.name:l for l in pixels(source)};a=full(lookup[SOURCE_LAYER]);parts,records=extract(a)
 for n,b in parts.items():Image.fromarray(b).save(OUT/'layers'/(n+'.png'))
 for n,path in PATHS.items():Image.fromarray((mask(path)*255).astype('uint8')).save(OUT/'masks'/(n+'.png'))
 psd=PSDImage.new('RGBA',(2048,2048),color=0);clone(source,psd,psd,[]);old=next(l for l in pixels(psd) if l.name==SOURCE_LAYER);parent=old.parent;index=list(parent).index(old)
 for n,b in parts.items():
  new=add(psd,parent,Image.fromarray(b),n);parent.remove(new);parent.insert(index,new);index+=1
 old.visible=False;path=OUT/'Rurino_Right_Fringe_Visible_Split_v034.psd';psd.save(path);saved=PSDImage.open(path);after={l.name:l for l in pixels(saved)}
 for n,orig in lookup.items():
  new=after[n];assert new.offset==orig.offset and np.array_equal(np.array(new.topil()),np.array(orig.topil())),n
  assert (new.opacity,new.blend_mode,new.clipping_layer)==(orig.opacity,orig.blend_mode,orig.clipping_layer),n
  assert new.visible==(False if n==SOURCE_LAYER else orig.visible),n
 for n,b in parts.items():assert np.array_equal(full(after[n]),b),n
 states=[]
 for state in ['Open','Half','Closed']:
  for doc in [source,saved]:
   for g in doc:
    if g.name.startswith('02_'):g.visible=g.name=='02_'+state
  before=np.array(source.composite(force=True));actual=np.array(saved.composite(force=True));assert np.array_equal(before,actual),state
  states.append({'state':state,'whole_composite_rgba_exact':True})
  if state=='Open':head=actual;Image.fromarray(actual).save(OUT/'qa/saved-psd-open.png')
 previews({n:full(after[n]) for n in parts},a,head)
 report={'input_psd_sha256':sha(SOURCE),'saved_psd_sha256':sha(path),'pixel_layers':len(after),'original_66_layers_retained':True,'source_layer_hidden':SOURCE_LAYER,'visible_lower_branches':records,'shared_remainder_retained':True,'new_parts_match_saved_pngs':True,'states':states,'completed_rooted_strands':0,'crown_fringe_separation_completed':False,'rejected_72_layer_candidate_used':False,'limitations':['upper closures are provisional construction seams and remain review candidates','residual contour slivers and source skin contamination remain in the shared review layer; edge ownership is not final','source boundary and brow gaps are retained, not reconstructed','the two lower branches are not complete independently riggable strands','crown, left fringe and remaining right-fringe connections are unresolved','no paint, mesh or physics added']}
 (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
