"""Assemble anatomical ponytail components from the pre-rejected 54-layer source.
No invented strand counts, new painting, root reconstruction or animation.
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
OUT=TURN/'hair_structure_assembly'
FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
SMALL={
 'L':['L01_Complete_Joined','L03_MiddleDrop','L01_RootBoundary_Cleaned','L02_RootExtended_LOCAL_PAINT'],
 'R':['R01_Complete_Joined','R03_Outline_Reassigned_VISIBLE_ONLY','R02_InnerEdge_Refined','R04_MainDrop','R05_InnerLock','R01_RootBoundary_Ownership_Cleaned'],
}
LARGE_PATH={
 'L':'M 210 470 L 334 490 Q 338 552 364 600 Q 381 625 387 640 Q 379 669 371 689 Q 344 711 298 723 Q 264 723 236 738 Q 205 752 198 790 Q 158 875 110 1024 L 110 1100 L -30 1100 L -30 870 Q 118 728 178 593 Q 202 534 210 470 Z',
 'R':'M 646 490 L 851 470 Q 876 634 969 790 L 1050 870 L 1050 1100 L 916 1100 L 916 1024 Q 875 870 838 813 Q 816 773 787 739 L 787 723 Q 737 714 679 692 Q 660 642 651 589 Q 646 545 646 490 Z',
}

SMALL_PATH={
 'L':'M 100 70 L 278 70 L 278 130 Q 250 180 238 230 Q 224 280 217 335 Q 211 390 219 440 Q 228 475 246 510 L 240 540 L 70 540 Z',
 'R':'M 760 70 L 1010 70 L 1010 550 L 741 550 L 745 520 Q 755 465 755 400 Q 775 330 748 240 Q 727 185 708 150 L 708 70 Z',
}

def merge(arrays):
 out=Image.new('RGBA',(2048,2048))
 for a in arrays:out.alpha_composite(Image.fromarray(a))
 return np.array(out)

def draw_sheet(items,path):
 sheet=Image.new('RGB',(1440,1100),'#e9eef4');d=ImageDraw.Draw(sheet);font=ImageFont.truetype(FONT,22)
 for i,(label,a) in enumerate(items):
  x=(i%2)*720;y=(i//2)*530;d.text((x+18,y+12),label,font=font,fill='#26384b')
  for cy in range(y+50,y+510,20):
   for cx in range(x+12,x+708,20):d.rectangle((cx,cy,cx+19,cy+19),fill='#ced7e2' if (cx//20+cy//20)%2 else '#e8edf3')
  # Same source viewport/scale for the two small tails and for the two large.
  box=(140,160,1950,1050) if i<2 else (0,970,2048,2048)
  im=Image.fromarray(a).crop(box);scale=min(675/im.width,445/im.height);im=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.LANCZOS)
  sheet.paste(im,(x+(720-im.width)//2,y+60),im)
 d.text((18,1060),'四条马尾的可见组件；未补隐藏根部，未做内部逐缕分割或物理。',font=font,fill='#52647a');sheet.save(path,quality=96)

def main():
 for f in ['layers','qa','masks']:(OUT/f).mkdir(parents=True,exist_ok=True)
 source=PSDImage.open(SOURCE);lookup={l.name:l for l in pixels(source)}
 parts={};excluded={};records=[]
 for side,names in SMALL.items():
  assembled=merge([full(lookup[n]) for n in names]);region=mask(SMALL_PATH[side])
  keep=assembled.copy();keep[~region]=0;review=assembled.copy();review[region]=0
  parts['SmallTwinTail_'+side+'_Visible']=keep
  excluded['SmallTwinTail_'+side+'_Boundary_REVIEW']=review
  records.append({'component':'SmallTwinTail_'+side+'_Visible','source_layers':names,'kind':'small ponytail visible assembly; outer/inner boundary candidate with excluded pixels retained','boundary_path_1024':SMALL_PATH[side]})
 for side,path in LARGE_PATH.items():
  name='RearTail_Image'+('Left' if side=='L' else 'Right')+'_Visible';a=full(lookup[name]);a[a[:,:,3]==0]=0;region=mask(path)
  if side=='R':
   # Visible burgundy garment residuals are review pixels, not hair.
   yy=np.indices(region.shape)[0];r,g,b=a[:,:,:3].transpose(2,0,1)
   garment=(yy>1400)&(r<190)&(g<140)&(b<180)&(a[:,:,3]>0)
   region &= ~garment
  keep=a.copy();keep[~region]=0;review=a.copy();review[region]=0
  parts['LargeTwinTail_'+side+'_Visible']=keep;excluded['LargeTwinTail_'+side+'_Boundary_REVIEW']=review
  assert np.array_equal(merge([keep,review]),a)
  records.append({'component':'LargeTwinTail_'+side+'_Visible','source_layers':[name],'kind':'visible silhouette ownership; excluded pixels retained separately','review_alpha_pixels':int((review[:,:,3]>0).sum()),'path_1024':path})
 for name,a in {**parts,**excluded}.items():Image.fromarray(a).save(OUT/'layers'/(name+'.png'))
 psd=PSDImage.new('RGBA',(2048,2048),color=0);clone(source,psd,psd,[]);dest={l.name:l for l in pixels(psd)};hidden=[]
 # Small tails replace their old inner groups. Their prior outer flick layers
 # were behind the head; moving the merged result must pass full RGBA QA.
 for side,names in SMALL.items():
  old=dest[names[1]];parent=old.parent
  layer=add(psd,parent,Image.fromarray(parts['SmallTwinTail_'+side+'_Visible']),'SmallTwinTail_'+side+'_Visible')
  review_name='SmallTwinTail_'+side+'_Boundary_REVIEW'
  add(psd,parent,Image.fromarray(excluded[review_name]),review_name)
  for n in names:dest[n].visible=False;hidden.append(n)
  parent.name='03_SmallTwinTail_'+side+'_SourcesAndAssembly'
 for side in ['L','R']:
  name='RearTail_Image'+('Left' if side=='L' else 'Right')+'_Visible';old=dest[name];parent=old.parent;index=list(parent).index(old)
  g=Group.new('04_LargeTwinTail_'+side+'_VisibleAndReview',parent=parent);parent.remove(g);parent.insert(index,g)
  for n in ['LargeTwinTail_'+side+'_Visible','LargeTwinTail_'+side+'_Boundary_REVIEW']:
   a=parts[n] if n in parts else excluded[n]
   if np.any(a[:,:,3]):add(psd,g,Image.fromarray(a),n)
  old.visible=False;hidden.append(name)
 # Preserve all drawing order. Crown/fringe and junctions get local folders,
 # not a false global regrouping that could alter occlusion.
 wrappers={
  'Bang_ImageLeft_Visible':'01_02_CrownFringe_L_SHARED_PENDING',
  'Bang_ImageRight_Visible':'01_02_CrownFringe_R_SHARED_PENDING',
  'CheekLock_ImageLeft':'Junction_Cheek_L_PENDING',
  'CheekLock_ImageRight':'Junction_Cheek_R_PENDING',
  'TempleLock_ImageRight':'Junction_Temple_R_PENDING',
  'LongFrontLock_ImageRight':'Junction_ThinFront_R_PENDING',
 }
 for n,label in wrappers.items():
  old=dest[n];parent=old.parent;index=list(parent).index(old);parent.remove(old)
  g=Group.new(label,parent=parent);parent.remove(g);parent.insert(index,g);g.append(old)
 path=OUT/'Rurino_Hair_Structure_Assembly_v034.psd';psd.save(path);saved=PSDImage.open(path);after={l.name:l for l in pixels(saved)}
 for n,old in lookup.items():
  new=after[n];assert old.offset==new.offset and np.array_equal(np.array(old.topil()),np.array(new.topil())),n
  assert (old.opacity,old.blend_mode,old.clipping_layer)==(new.opacity,new.blend_mode,new.clipping_layer),n
  assert new.visible==(False if n in hidden else old.visible),n
 for n,a in {**parts,**excluded}.items():
  if n in after:assert np.array_equal(full(after[n]),a),n
 checks=[]
 for state in ['Open','Half','Closed']:
  for doc in [source,saved]:
   for g in doc:
    if g.name.startswith('02_'):g.visible=g.name=='02_'+state
  a=np.array(source.composite(force=True));b=np.array(saved.composite(force=True));delta=np.abs(a.astype('int16')-b.astype('int16'))
  small_support=(parts['SmallTwinTail_L_Visible'][:,:,3]>0)|(parts['SmallTwinTail_R_Visible'][:,:,3]>0)|(excluded['SmallTwinTail_L_Boundary_REVIEW'][:,:,3]>0)|(excluded['SmallTwinTail_R_Boundary_REVIEW'][:,:,3]>0)
  assert delta.max()<=1,(state,int(delta.max()))
  assert not delta[~small_support].any(),state
  assert not ((a[:,:,3]==0)&(b[:,:,3]>0)).any(),state
  assert not ((a[:,:,3]==255)&(b[:,:,3]<254)).any(),state
  checks.append({'state':state,'full_rgba_max_difference':int(delta.max()),'changed_pixels':int(np.any(delta,axis=2).sum()),'opaque_alpha_rounded_to_254':int(((a[:,:,3]==255)&(b[:,:,3]==254)).sum()),'difference_outside_small_tail_support':0,'note':'8-bit alpha flattening rounds small-tail overlaps by at most 1/255; all other pixels exact'})
  if state=='Open':Image.fromarray(b).save(OUT/'qa/saved-psd-open.png')
 draw_sheet([(label,parts[n]) for label,n in [('小双马尾 · 画面左','SmallTwinTail_L_Visible'),('小双马尾 · 画面右','SmallTwinTail_R_Visible'),('大双马尾 · 画面左','LargeTwinTail_L_Visible'),('大双马尾 · 画面右','LargeTwinTail_R_Visible')]],OUT/'qa/four-ponytail-components.jpg')
 # Anatomical guide uses labelled pointers, not fabricated segmentation lines.
 im=Image.open(OUT/'qa/saved-psd-open.png').resize((1024,1024));guide=Image.new('RGB',(1480,1120),'#e8edf4');guide.paste(im,(225,48),im);d=ImageDraw.Draw(guide);font=ImageFont.truetype(FONT,23)
 labels=[('① 头顶',(22,35),(720,125)),('② 刘海',(20,190),(752,320)),('③ 左小马尾',(12,380),(407,410)),('③ 右小马尾',(1260,380),(1084,427)),('④ 左大马尾',(12,840),(380,835)),('④ 右大马尾',(1260,840),(1115,831))]
 for label,xy,point in labels:
  d.text(xy,label,font=font,fill='#26394e');start=(xy[0]+175 if xy[0]<225 else xy[0]-8,xy[1]+16);d.line([start,point],fill='#98436d',width=3);x,y=point;d.ellipse((x-5,y-5,x+5,y+5),fill='#98436d')
 d.text((245,1076),'头顶↔刘海共用发面、鬓边连接和扎点隐藏处仍待辨认。',font=font,fill='#52647a');guide.save(OUT/'qa/four-part-structure-guide.jpg',quality=96)
 report={'source_psd_sha256':sha(SOURCE),'saved_psd_sha256':sha(path),'pixel_layers':len(after),'original_54_layers_retained':True,'newly_hidden_originals':hidden,'components':records,'states':checks,'classification':['crown','fringe','small twin ponytails L/R','large twin ponytails L/R'],'crown_fringe_separation_completed':False,'fine_strand_split_completed':False,'limitations':['crown/fringe common surface remains explicitly shared','cheek/temple/thin-front junctions remain pending','old source boundary contamination still needs review','small-tail modules inherit prior root experiments; hidden roots not anatomically validated','large tails are visible portions only and extend beyond canvas','no rig or physics'],'rejected_72_layer_candidate_used':False}
 (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k not in ['components','newly_hidden_originals']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
