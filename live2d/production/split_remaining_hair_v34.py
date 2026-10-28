"""Partition the remaining visible bangs, cheek locks and ponytails along flow.
This is an editable ownership pass. No repainting, hidden-root invention or rig.
"""
import json
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from psd_tools import PSDImage
from psd_tools.api.layers import Group
from split_head_v34 import mask
from split_left_head_parts_v34 import TURN,pixels,clone,add,sha
from build_hair_flow_redraw_v34 import full
SOURCE=TURN/'hair_drop_ownership/Rurino_Left_Head_Hair_Edges_v034.psd'
OUT=TURN/'remaining_hair_split'
FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
# Curves traced in the 1024 reference. A left-side region closes outside the
# canvas; its straight closure never cuts the source. Interior boundaries are
# longitudinal curves following each illustrated lock, not uniform strips.
def left(path):return mask('M 0 0 L '+path+' L 0 1100 Z')
CONFIG={
 'Bang_ImageLeft_Visible':('BL','左刘海',[
  '435 0 L 435 85 C 393 111 346 156 319 209 C 291 264 286 326 309 381 L 309 1100',
 ]),
 'Bang_ImageRight_Visible':('BR','右刘海',[
  '436 0 L 436 88 C 466 144 492 212 495 275 C 498 322 489 365 477 391 L 477 1100',
  '451 0 L 451 78 C 491 107 530 165 550 215 C 581 280 585 331 551 376 L 551 1100',
  '470 0 L 470 72 C 531 103 577 165 596 229 C 615 294 610 347 574 396 L 574 1100',
 ]),
 'CheekLock_ImageLeft':('CL','左贴脸发',[
  '347 0 L 347 112 C 303 174 265 279 251 363 C 239 439 264 519 296 567 C 315 597 340 624 367 645 L 367 1100',
  '369 0 L 369 100 C 324 158 288 250 279 329 C 271 404 289 477 313 519 Q 324 537 336 545 L 336 1100',
 ]),
 'CheekLock_ImageRight':('CR','右贴脸发',[
  '551 0 L 551 77 C 606 123 639 190 644 260 C 650 342 629 418 601 461 Q 582 508 559 530 L 559 1100',
  '565 0 L 565 88 C 626 130 674 207 680 290 C 687 386 661 482 622 547 Q 588 607 551 636 L 551 1100',
 ]),
 'RearTail_ImageLeft_Visible':('TL','左长马尾可见段',[
  '290 0 L 290 480 C 277 557 246 652 207 730 C 161 819 109 909 84 1024 L 84 1100',
  '340 0 L 340 500 C 338 567 321 640 297 708 C 260 806 211 904 182 1024 L 182 1100',
 ]),
 'RearTail_ImageRight_Visible':('TR','右长马尾可见段',[
  '679 0 L 679 485 C 677 548 688 615 712 691 C 740 782 785 894 835 1024 L 835 1100',
  '783 0 L 783 490 C 799 570 822 654 861 724 C 917 821 977 917 1008 1024 L 1008 1100',
 ]),
}

def checker(size):
 im=Image.new('RGB',size,'#e8edf3');d=ImageDraw.Draw(im)
 for y in range(0,size[1],20):
  for x in range(0,size[0],20):
   if (x//20+y//20)%2:d.rectangle((x,y,x+19,y+19),fill='#ced8e3')
 return im

def main():
 for folder in ['layers','masks','qa']:(OUT/folder).mkdir(parents=True,exist_ok=True)
 source=PSDImage.open(SOURCE);lookup={l.name:l for l in pixels(source)};splits={};records=[]
 for parent,(prefix,label,curves) in CONFIG.items():
  original=full(lookup[parent]);original[original[:,:,3]==0]=0;claimed=np.zeros((2048,2048),bool);parts=[];recon=np.zeros_like(original)
  for index,region in enumerate([left(c) for c in curves]+[np.ones((2048,2048),bool)]):
   region &= ~claimed;claimed|=region
   arr=original.copy();arr[~region]=0
   name=f'{prefix}{index+1:02d}_Visible_ONLY';assert np.any(arr[:,:,3]),name
   recon[region]=arr[region];parts.append((name,arr));Image.fromarray(arr).save(OUT/'layers'/(name+'.png'))
   Image.fromarray((region*255).astype('uint8')).save(OUT/'masks'/(name+'.png'))
   records.append({'name':name,'source':parent,'label':f'{label} {index+1:02d}','bbox':list(Image.fromarray(arr).getbbox()),'alpha_pixels':int((arr[:,:,3]>0).sum()),'status':'visible ownership split only; shared roots, hidden overlap and source contamination deferred'})
  assert np.array_equal(recon,original),parent
  splits[parent]=parts
 psd=PSDImage.new('RGBA',(2048,2048),color=0);clone(source,psd,psd,[]);dest={l.name:l for l in pixels(psd)}
 for parent,parts in splits.items():
  old=dest[parent];owner=old.parent;index=list(owner).index(old)
  group=Group.new(parent+'_FlowSplit',parent=owner);owner.remove(group);owner.insert(index,group)
  group.opacity=old.opacity;group.blend_mode=old.blend_mode;group.visible=old.visible
  for name,arr in parts:add(psd,group,Image.fromarray(arr),name)
  old.visible=False
 path=OUT/'Rurino_Left_Head_Remaining_Hair_Split_v034.psd';psd.save(path);saved=PSDImage.open(path);after={l.name:l for l in pixels(saved)}
 assert len(after)==54+len(records)
 for name,old in lookup.items():
  new=after[name];assert old.offset==new.offset and np.array_equal(np.array(old.topil()),np.array(new.topil())),name
  assert (old.opacity,old.blend_mode,old.clipping_layer)==(new.opacity,new.blend_mode,new.clipping_layer),name
  assert new.visible==(False if name in CONFIG else old.visible),name
 for parts in splits.values():
  for name,arr in parts:assert np.array_equal(full(after[name]),arr),name
 checks=[]
 for state in ['Open','Half','Closed']:
  for doc in [source,saved]:
   for g in doc:
    if g.name.startswith('02_'):g.visible=g.name=='02_'+state
  a=np.array(source.composite(force=True));b=np.array(saved.composite(force=True));delta=np.abs(a.astype('int16')-b.astype('int16'))
  assert not delta.any(),(state,int(delta.max()))
  checks.append({'state':state,'full_composite_rgba_max_difference':int(delta.max())})
  if state=='Open':Image.fromarray(b).save(OUT/'qa/saved-psd-open.png')
 font=ImageFont.truetype(FONT,19)
 # Each sheet shows the actual independent alphas at one shared source scale.
 for sheetno,parents in enumerate([list(CONFIG)[:2],list(CONFIG)[2:4],list(CONFIG)[4:]]):
  cells=[]
  for parent in parents:
   parts=splits[parent];allbox=Image.fromarray(full(lookup[parent])).getbbox()
   for name,arr in parts:cells.append((next(r['label'] for r in records if r['name']==name),name,arr,allbox))
  cols=3;rows=(len(cells)+cols-1)//cols;sheet=Image.new('RGB',(1440,rows*550+60),'#edf1f6');d=ImageDraw.Draw(sheet)
  for i,(label,name,arr,box) in enumerate(cells):
   x=i%cols*480;y=i//cols*550
   sheet.paste(checker((460,480)),(x+10,y+50));d.text((x+12,y+12),name+' · '+label,font=font,fill='#27364b')
   im=Image.fromarray(arr).crop(box);scale=min(440/im.width,460/im.height);im=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.LANCZOS);sheet.paste(im,(x+(480-im.width)//2,y+60),im)
  d.text((15,rows*550+12),'实际透明图层；同一来源组使用相同比例。仅拆可见段，补根与边缘统一后修。',font=font,fill='#4b5b70')
  sheet.save(OUT/'qa'/(['bangs-alpha.jpg','cheeks-alpha.jpg','tails-alpha.jpg'][sheetno]),quality=96)
 # Source-space colour map makes traced flow boundaries reviewable without
 # claiming an isolated cut is a finished, paint-complete strand.
 base=Image.open(OUT/'qa/saved-psd-open.png').convert('RGBA');canvas=Image.new('RGBA',base.size,'#d2dae3');canvas.alpha_composite(base)
 palette=[(245,92,120),(70,190,230),(255,185,64),(133,123,238)]
 for parent,parts in splits.items():
  for i,(name,arr) in enumerate(parts):
   overlay=np.zeros_like(arr);overlay[:,:,:3]=palette[i%len(palette)];overlay[:,:,3]=(arr[:,:,3]>0)*75;canvas.alpha_composite(Image.fromarray(overlay))
 canvas.resize((1024,1024)).convert('RGB').save(OUT/'qa/hair-split-location.jpg',quality=96)
 report={'input_psd_sha256':sha(SOURCE),'saved_psd_sha256':sha(path),'pixel_layers':len(after),'source_pixel_layers_retained':54,'source_groups_split':len(CONFIG),'new_visible_parts':len(records),'original_layers_newly_hidden':list(CONFIG),'source_visible_rgba_and_alpha_reconstruct_exactly':True,'new_parts_zero_hidden_rgb_at_alpha_zero':True,'new_layers_match_saved_pngs':True,'state_checks':checks,'parts':records,'trace_curves_1024':{k:v[2] for k,v in CONFIG.items()},'limitations':['visible-source partition only; roots and hidden motion overlap not painted','inherited eyebrow/flower/boundary contamination is deferred for joint cleanup','long ponytails extend beyond source frame; no complete tail tips inferred','temple strand and thin front strand already isolated, retained unchanged','no Cubism mesh or physics added'],'user_work_order':'split remaining hair first; repair seams, roots and shapes together afterward'}
 (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k not in ['parts','trace_curves_1024']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
