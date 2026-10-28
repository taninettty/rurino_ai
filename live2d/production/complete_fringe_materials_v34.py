"""Restore source-backed fringe paint and add limited concealed edge padding.
Keep left/right common fringe plates whole. This is local raster work, not a rig.
"""
import json
from pathlib import Path
import cv2,numpy as np
from scipy.ndimage import distance_transform_edt
from PIL import Image,ImageDraw,ImageFont
from psd_tools import PSDImage
from split_head_v34 import mask
from split_left_head_parts_v34 import TURN,pixels,clone,add,sha
from build_hair_flow_redraw_v34 import full
SOURCE=TURN/'brows_clean_fringe_repair/Rurino_Brows_Separated_Fringe_Repaired_v034.psd'
OUT=TURN/'fringe_material_completion';FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
NAMES={s:f'CrownFringe_{s}_BrowRemoved_REPAIRED' for s in ['L','R']}
# Only the narrow disconnected flower-edge trail is excluded here. The margin
# follows the empty space next to the principal hair mass, not a new strand cut.
STRIP='M 0 90 L 382 90 L 368 100 L 344 120 L 324 140 L 312 160 L 301 180 L 291 200 L 280 230 L 268 270 L 255 330 L 0 330 Z'
SKIN={
'L':'M 423 147 Q 412 161 404 173 L 400 190 L 452 190 L 452 140 L 440 140 Q 431 144 423 147 Z',
'R':'M 420 120 L 436 120 Q 449 164 458 211 L 455 215 L 420 215 Z',
}
SKIN_R_TIP='M 603 342 Q 590 374 571 392 L 600 410 L 624 401 C 609 387 605 365 603 342 Z'
# These gaps have visible source paint in the composed head; recover it instead
# of synthesizing an invented root. Upper fill stays inside the known hair area.
RECOVER={
'L':['M 427 60 Q 390 75 360 100 Q 337 120 299 163 Q 292 185 297 205 Q 300 213 300 221 L 321 224 L 352 141 L 398 105 L 494 60 Z'],
'R':[
'M 498 63 Q 551 51 598 69 Q 624 80 647 96 L 649 106 C 635 117 621 136 614 166 L 606 181 L 575 134 L 541 102 Z',
'M 537 334 Q 549 355 547 377 C 565 362 578 335 579 309 L 575 300 L 535 325 Z',
'M 580 316 C 580 343 577 371 571 391 C 588 375 601 351 603 337 L 600 310 Z',
]}
# Small concealed backing only, not claimed complete unseen anatomy.
PAD_WINDOW={
'L':'M 405 154 L 429 146 L 441 166 L 429 184 L 402 182 Z',
'R':'M 435 143 L 450 141 L 467 211 L 450 211 Z',
}

def checker(size):
 yy,xx=np.indices((size[1],size[0]));a=np.where(((xx//18+yy//18)%2)[:,:,None],np.array([201,212,224]),np.array([234,239,245]));return Image.fromarray(a.astype('uint8'))

def prepare():
 for f in ['layers','masks','qa']:(OUT/f).mkdir(parents=True,exist_ok=True)
 head=np.array(Image.open(TURN/'brows_clean_fringe_repair/qa/saved-psd-brows-hidden.png').convert('RGBA'))
 source=PSDImage.open(SOURCE);eye_coverage=np.zeros((2048,2048),bool)
 for g in source:
  if g.name.startswith('02_'):
   for l in pixels(g):eye_coverage|=full(l)[:,:,3]>0
 foreground=full(next(l for l in pixels(source) if l.name=='Foreground_Hair_Overlap'))[:,:,3]>250
 outputs={};records=[]
 for s,n in NAMES.items():
  a=np.array(Image.open(TURN/'brows_clean_fringe_repair/layers'/(n+'.png')));a[a[:,:,3]==0]=0
  exclude=mask(SKIN[s])
  if s=='L':exclude|=mask(STRIP)
  else:exclude|=mask(SKIN_R_TIP)
  clean=a.copy();clean[exclude]=0;context=a.copy();context[~exclude]=0
  recovered=np.zeros_like(a);support=np.zeros((2048,2048),bool)
  for path in RECOVER[s]:support|=mask(path)
  # Existing opaque hair stays untouched; known missing source paint is restored.
  skin_exclude=mask(SKIN[s])
  if s=='R':skin_exclude|=mask(SKIN_R_TIP)
  support&=(clean[:,:,3]<250)&(head[:,:,3]>250)&~skin_exclude
  support&=(~eye_coverage)|foreground
  # Reject dark lash/sclera contamination at tip boundaries even outside eye masks.
  support&=(head[:,:,:3].mean(axis=2)>85)&(head[:,:,0].astype('int16')>=head[:,:,2].astype('int16')-2)
  recovered[support]=head[support]
  material=clean.copy();material[support]=head[support]
  # Concealed small margin uses interior hair colour, avoiding dark outlines.
  opaque=material[:,:,3]>250;dist,nearest=distance_transform_edt(~opaque,return_indices=True)
  yy,xx=np.indices((2048,2048));cx,cy,rx,ry=(836,332,50,48) if s=='L' else (898,354,28,76)
  taper=np.clip(1-((xx-cx)/rx)**2-((yy-cy)/ry)**2,0,1)
  padding=(dist>0)&(dist<=16*taper)&(head[:,:,3]>250)
  interior=cv2.erode(opaque.astype('uint8'),np.ones((13,13),np.uint8))>0
  _,inside=distance_transform_edt(~interior,return_indices=True)
  backing=np.zeros_like(a);py,px=np.where(padding);sx=np.clip(px+(-28 if s=='L' else 36),0,2047);sy=py.copy();bad=material[sy,sx,3]<250;sx[bad]=inside[1][py[bad],px[bad]];sy[bad]=inside[0][py[bad],px[bad]]
  backing[py,px,:3]=material[sy,sx,:3];backing[py,px,3]=255
  # Keep backing separate and hidden in default static assembly for review.
  complete=backing.copy();im=Image.fromarray(complete);im.alpha_composite(Image.fromarray(material));complete=np.array(im)
  outputs[s]={'original':a,'clean':clean,'context':context,'recovered':recovered,'visible':material,'backing':backing,'material':complete}
  for k,b in outputs[s].items():
   if k!='original':Image.fromarray(b).save(OUT/'layers'/f'Fringe_{s}_{k}.png')
  Image.fromarray((exclude*255).astype('uint8')).save(OUT/'masks'/f'{s}-reassigned-context.png')
  Image.fromarray((support*255).astype('uint8')).save(OUT/'masks'/f'{s}-source-recovery.png')
  Image.fromarray((padding*255).astype('uint8')).save(OUT/'masks'/f'{s}-concealed-padding.png')
  records.append({'side':s,'reassigned_context_pixels':int((context[:,:,3]>0).sum()),'source_recovered_pixels':int(support.sum()),'concealed_padding_pixels':int(padding.sum()),'max_padding_native_pixels':16,'fringe_further_split':False})
 previews(outputs);return outputs,records

def previews(outputs):
 sheet=Image.new('RGB',(1440,1640),'#e8edf3');d=ImageDraw.Draw(sheet);font=ImageFont.truetype(FONT,20)
 for row,s in enumerate(['L','R']):
  items=[('原独立层',outputs[s]['original']),('清理 + 原画补回 + 小范围遮挡余量',outputs[s]['material']),('移出的花饰 / 肤色等上下文',outputs[s]['context'])]
  # Shared viewport per side contains every nontransparent source/output pixel.
  union=np.maximum.reduce([b[:,:,3] for _,b in items]);box=Image.fromarray(union).getbbox();box=(box[0]-12,box[1]-12,box[2]+12,box[3]+12)
  for col,(label,b) in enumerate(items):
   x=col*480;y=row*820;tile=checker((460,730));im=Image.fromarray(b).crop(box);im.thumbnail((445,710));tile.paste(im,((460-im.width)//2,(730-im.height)//2),im);sheet.paste(tile,(x+10,y+60));d.text((x+10,y+18),s+' · '+label,font=font,fill='#26394c')
  d.text((15,row*820+790),'实际透明层；左右共用发面保持整体。中列含待检查的隐藏补边，不代表全头发已完成。',font=font,fill='#52647a')
 sheet.save(OUT/'qa/fringe-materials-comparison.jpg',quality=97)



def main():
 outputs,records=prepare();source=PSDImage.open(SOURCE);lookup={l.name:l for l in pixels(source)}
 psd=PSDImage.new('RGBA',(2048,2048),color=0);clone(source,psd,psd,[]);dest={l.name:l for l in pixels(psd)}
 expected={};edit=np.zeros((2048,2048),bool)
 for s,n in NAMES.items():
  old=dest[n];parent=old.parent;index=list(parent).index(old)
  for key,label in [('visible',f'Fringe_{s}_SourceRestored_WHOLE'),('context',f'Fringe_{s}_NonHairContext_PRESERVED')]:
   arr=outputs[s][key];new=add(psd,parent,Image.fromarray(arr),label);parent.remove(new);parent.insert(index,new);index+=1;expected[label]=arr
  old.visible=False;edit|=outputs[s]['recovered'][:,:,3]>0
 from psd_tools.api.layers import Group
 review=Group.new('05_Fringe_ConcealedMargins_REVIEW_OFF',parent=psd);review.visible=False
 for s in NAMES:
  name=f'Fringe_{s}_ConcealedMargin_LOCAL';arr=outputs[s]['backing'];add(psd,review,Image.fromarray(arr),name);expected[name]=arr
 path=OUT/'Rurino_Fringe_SourceRestored_v034.psd';psd.save(path);saved=PSDImage.open(path);after={l.name:l for l in pixels(saved)}
 for n,old in lookup.items():
  new=after[n];assert old.offset==new.offset and np.array_equal(np.array(old.topil()),np.array(new.topil())),n
  assert (old.opacity,old.blend_mode,old.clipping_layer)==(new.opacity,new.blend_mode,new.clipping_layer),n
  assert new.visible==(False if n in NAMES.values() else old.visible),n
 for n,arr in expected.items():assert np.array_equal(full(after[n]),arr),n
 states=[]
 for state in ['Open','Half','Closed']:
  for doc in [source,saved]:
   for g in doc:
    if g.name.startswith('02_'):g.visible=g.name=='02_'+state
  before=np.array(source.composite(force=True));actual=np.array(saved.composite(force=True));diff=np.abs(actual.astype('int16')-before.astype('int16'));assert not diff[~edit].any(),state
  assert diff.max()<64,(state,int(diff.max()))
  states.append({'state':state,'outside_recovery_mask_exact':True,'changed_pixels':int(np.any(diff,axis=2).sum()),'max_channel_difference':int(diff.max())})
  if state=='Open':Image.fromarray(actual).save(OUT/'qa/saved-psd-open.png')
 # Read back both new visible layers, preserving the full isolated-material QA.
 for s in NAMES:
  outputs[s]['visible']=full(after[f'Fringe_{s}_SourceRestored_WHOLE']);outputs[s]['context']=full(after[f'Fringe_{s}_NonHairContext_PRESERVED']);outputs[s]['backing']=full(after[f'Fringe_{s}_ConcealedMargin_LOCAL'])
  im=Image.fromarray(outputs[s]['backing']);im.alpha_composite(Image.fromarray(outputs[s]['visible']));outputs[s]['material']=np.array(im)
 previews(outputs)
 report={'input_psd_sha256':sha(SOURCE),'saved_psd_sha256':sha(path),'pixel_layers':len(after),'original_71_layers_retained':True,'independent_brows_preserved':True,'new_layers_match_pngs':True,'fringe_parts':records,'states':states,'source_recovery_image':'../brows_clean_fringe_repair/qa/saved-psd-brows-hidden.png','source_recovery_sha256':sha(TURN/'brows_clean_fringe_repair/qa/saved-psd-brows-hidden.png'),'concealed_margin_default_visibility':False,'method':'local source-pixel recovery, non-hair context reassignment, limited interior-colour concealed backing','limitations':['only current left-turn fringe materials advanced','concealed padding is limited to 16 native pixels and has not passed motion checks','shared crown and remaining lower fringe/temple seams still need repair','small/large ponytail roots and body-hidden hair not completed','no new generative task, mesh or physics; C/D subdivision not used']}
 (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
