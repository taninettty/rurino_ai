"""Recover misclassified hairline pixels and paint local crown overlap margins.
The visible hairline is source-backed. Concealed extensions are review-only.
"""
import argparse,json
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
from psd_tools import PSDImage
from psd_tools.api.layers import Group
from complete_hair_backplates_v34 import combine,protected_face_mask
from complete_fringe_materials_v34 import checker,FONT
from split_head_v34 import mask
from split_left_head_parts_v34 import TURN,pixels,clone,add,sha
from build_hair_flow_redraw_v34 import full
SOURCE=TURN/'hair_concealed_completion/Rurino_Hair_Concealed_Backings_v034.psd'
OUT=TURN/'crown_root_completion'
# Native 2048 coordinates: select the actual hair island, not the flower trail.
# Right boundary stops at the upper hairline tips; lower cast shadow stays on skin.
HAIRLINE={
'L':[(790,270),(910,270),(910,370),(790,370)],
'R':[(870,294),(900,294),(905,353),(900,355),(896,356),(894,356),(894,353),(886,355),(881,356),(873,347),(868,341)]}
# 1024-coordinate Bezier outlines follow each existing occluded junction.
# These are overlap margins, not newly invented strands.
PADS={
'Flower_L':'M 329 119 Q 350 97 382 82 L 378 88 Q 347 109 327 130 Q 310 148 299 163 L 293 169 Q 307 139 329 119 Z',
'Flower_R':'M 644 81 Q 658 88 670 105 Q 677 118 670 134 Q 647 151 625 176 L 608 180 Q 614 142 638 116 L 650 105 Z',
}

def save(name,a,folder='layers'):Image.fromarray(a).save(OUT/folder/(name+'.png'))

def prepare(source):
 ls={l.name:l for l in pixels(source)};pieces={};records=[]
 original=combine(full(ls['Fringe_L_SourceRestored_WHOLE']),full(ls['Fringe_R_SourceRestored_WHOLE']))
 restored=original.copy();recovered_all=np.zeros_like(original)
 for side,points in HAIRLINE.items():
  ctx=full(ls[f'Fringe_{side}_NonHairContext_PRESERVED']);sel=Image.new('L',(2048,2048));ImageDraw.Draw(sel).polygon(points,fill=255);support=np.array(sel)>0
  hair=ctx.copy();hair[~support]=0;remaining=ctx.copy();remaining[support]=0
  assert np.array_equal(combine(remaining,hair),ctx)
  pieces[side]=(hair,remaining);restored=combine(restored,hair);recovered_all=combine(recovered_all,hair)
  save('Hairline_'+side+'_source',hair);save('Context_'+side+'_remaining',remaining);save('Hairline_'+side+'_mask',(support*255).astype('uint8'),'masks')
  records.append({'side':side,'source_context_layer':f'Fringe_{side}_NonHairContext_PRESERVED','recovered_original_hairline_pixels':int((hair[:,:,3]>0).sum()),'context_partition_exact':True,'native_selection_polygon':points})
 # Smooth local RGB continuation from the same source material. This does not
 # mirror either side or warp the visible original into a new head angle.
 valid=restored[:,:,3]>=250;weight=cv2.GaussianBlur(valid.astype('float32'),(0,0),16)
 average=np.stack([cv2.GaussianBlur(restored[:,:,k].astype('float32')*valid,(0,0),16)/np.maximum(weight,1e-7) for k in range(3)],axis=2)
 back=np.zeros_like(original);pad_records=[]
 for key,path in PADS.items():
  area=mask(path);support=area&(restored[:,:,3]<250)&(weight>.0003)
  arr=np.zeros_like(original);arr[support,:3]=np.rint(average[support]).clip(0,255).astype('uint8');arr[support,3]=255
  # A subpixel feather softens the newly painted boundary without changing the source.
  soft=cv2.GaussianBlur(area.astype('float32'),(0,0),.7);arr[support,3]=np.rint(soft[support]*255).astype('uint8');arr[arr[:,:,3]==0]=0
  back=combine(back,arr);save(key+'_concealed',arr);save(key+'_mask',(support*255).astype('uint8'),'masks')
  pad_records.append({'key':key,'painted_pixels':int((arr[:,:,3]>0).sum()),'path_1024':path})
 completed=combine(back,restored)
 for n,a in [('Crown_original',original),('Crown_hairline_restored',restored),('Hairline_recovered',recovered_all),('Crown_concealed',back),('Crown_complete_REVIEW',completed)]:save(n,a)
 # True isolated alpha layers, all three columns use one viewport and scale.
 box=(500,75,1380,900);sheet=Image.new('RGB',(1440,570),'#e8edf3');d=ImageDraw.Draw(sheet);font=ImageFont.truetype(FONT,20)
 for i,(label,a) in enumerate([('原独立头顶 / 刘海',original),('发际线恢复 + 遮挡边补画（检查稿）',completed),('本轮恢复的原画与新补边',combine(back,recovered_all))]):
  im=Image.fromarray(a).crop(box);im.thumbnail((454,460));bg=checker((460,460));bg.paste(im,((460-im.width)//2,(460-im.height)//2),im);sheet.paste(bg,(i*480+10,60));d.text((i*480+10,20),label,font=font,fill='#26394c')
 d.text((14,535),'中间保留露额，不再拆碎刘海。补边默认隐藏；本图是实际透明素材，尚未做动作验收。',font=font,fill='#52647a');sheet.save(OUT/'qa/crown-root-comparison.jpg',quality=97)
 box=(780,240,940,390);sheet=Image.new('RGB',(1000,500),'#e8edf3');d=ImageDraw.Draw(sheet)
 for i,(label,a) in enumerate([('恢复前：发际线被归入上下文',original),('恢复后：原画重新纳入头发',restored)]):
  im=Image.fromarray(a).crop(box).resize((480,450));bg=checker(im.size);bg.paste(im,(0,0),im);sheet.paste(bg,(i*500+10,45));d.text((i*500+12,12),label,font=font,fill='#26394c')
 sheet.save(OUT/'qa/hairline-recovery-detail.jpg',quality=97)
 return pieces,completed,records,pad_records

def main(prepare_only=False):
 for n in ['layers','masks','qa']:(OUT/n).mkdir(parents=True,exist_ok=True)
 source=PSDImage.open(SOURCE);pieces,completed,records,pads=prepare(source)
 if prepare_only:print(json.dumps({'recovered':records,'pads':pads},ensure_ascii=False));return
 ls={l.name:l for l in pixels(source)};psd=PSDImage.new('RGBA',(2048,2048),color=0);clone(source,psd,psd,[]);dest={l.name:l for l in pixels(psd)};expected={};replaced=[]
 for side,(hair,remaining) in pieces.items():
  name=f'Fringe_{side}_NonHairContext_PRESERVED';old=dest[name];parent=old.parent;idx=list(parent).index(old)
  for label,arr in [(f'Crown_Hairline_{side}_Recovered_SOURCE',hair),(f'Fringe_{side}_Context_AfterHairlineRecovery',remaining)]:
   new=add(psd,parent,Image.fromarray(arr),label);parent.remove(new);parent.insert(idx,new);idx+=1;expected[label]=arr
  old.visible=False;replaced.append(name)
 g=Group.new('08_Crown_ContinuousMaterial_REVIEW_OFF',parent=psd);g.visible=False;name='CrownFringe_Continuous_Completed_LOCAL_REVIEW';add(psd,g,Image.fromarray(completed),name);expected[name]=completed
 path=OUT/'Rurino_Crown_Roots_v034.psd';psd.save(path);saved=PSDImage.open(path);after={l.name:l for l in pixels(saved)}
 for n,old in ls.items():
  new=after[n];assert old.offset==new.offset and np.array_equal(np.array(old.topil()),np.array(new.topil())),n
  assert (old.opacity,old.blend_mode,old.clipping_layer)==(new.opacity,new.blend_mode,new.clipping_layer),n
  assert new.visible==(False if n in replaced else old.visible),n
 for n,a in expected.items():assert np.array_equal(full(after[n]),a),n
 states=[]
 for state in ['Open','Half','Closed']:
  for doc in [source,saved]:
   for g in doc:
    if g.name.startswith('02_'):g.visible=g.name=='02_'+state
  before=np.array(source.composite(force=True));actual=np.array(saved.composite(force=True));assert np.array_equal(before,actual),state
  states.append({'state':state,'default_composite_rgba_exact':True,'changed_pixels':0})
  if state=='Open':save('saved-psd-open',actual,'qa')
  print('Checked',state,flush=True)
 report={'input_psd_sha256':sha(SOURCE),'saved_psd_sha256':sha(path),'pixel_layers':len(after),'original_101_layer_pixels_and_properties_preserved':True,'original_context_layers_hidden':replaced,'new_layers_match_saved_pngs':True,'source_hairline_recovery':records,'concealed_review_pads':pads,'states':states,'review_group_default_visible':False,'method':'original source-pixel hairline reassignment, same-side smoothed colour continuation for two local occluded crown junctions; continuous crown/fringe review material','limitations':['hairline still derived from current left-view artwork, not front-view reconstruction','small lower hairline cast shadows remain with face context','new overlap margins hidden and not motion approved','shared crown/fringe retained together, not a separate fully rigged crown','lower-left fringe flat ownership cut still pending; rejected a tapered trial because its join was visible','large tail canvas-cropped tips and shoulder seams still pending','no new Cubism meshes, physics or runtime export'],'libtv_generation_used':False}
 (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--prepare-only',action='store_true');main(p.parse_args().prepare_only)
