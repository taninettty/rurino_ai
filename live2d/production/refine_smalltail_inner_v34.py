"""Separate foreground context from small tails, restore inner hair and pad concealed edges.
Raster material work only; no new generated art, Cubism mesh or physics.
"""
import json
import cv2,numpy as np
from scipy.ndimage import distance_transform_edt
from scipy.interpolate import PchipInterpolator
from PIL import Image,ImageDraw,ImageFont
from psd_tools import PSDImage
from split_left_head_parts_v34 import TURN,pixels,clone,add,sha
from build_hair_flow_redraw_v34 import full
from complete_fringe_materials_v34 import checker,FONT
SOURCE=TURN/'smalltail_root_completion/Rurino_SmallTwinTail_Roots_v034.psd'
OUT=TURN/'smalltail_inner_refinement'

def over(bottom,top):return np.array(Image.alpha_composite(Image.fromarray(bottom),Image.fromarray(top)))

def previews(parts):
 sheet=Image.new('RGB',(1440,1230),'#e8edf3');d=ImageDraw.Draw(sheet);font=ImageFont.truetype(FONT,20)
 for row,s in enumerate(['L','R']):
  a=parts[s];bbox=Image.fromarray(np.maximum(a['original'][:,:,3],a['complete'][:,:,3])).getbbox();bbox=(bbox[0]-12,bbox[1]-10,bbox[2]+12,bbox[3]+10)
  for col,(k,label) in enumerate([('original','原小马尾透明层'),('complete','内缘修整 + 遮挡余量'),('context','移出的前景 / 暖色上下文')]):
   x=480*col;y=590*row;tile=checker((460,510));im=Image.fromarray(a[k]).crop(bbox);im.thumbnail((445,500));tile.paste(im,((460-im.width)//2,(510-im.height)//2),im);sheet.paste(tile,(x+10,y+48));d.text((x+12,y+12),s+' · '+label,font=font,fill='#26394c')
 d.text((16,1180),'实际独立透明层；右侧接回既有内侧头发。补边最多 24 原尺寸像素，未通过运动验收。',font=font,fill='#52647a')
 sheet.save(OUT/'qa/smalltail-inner-comparison.jpg',quality=97)

def main():
 for f in ['layers','masks','qa']:(OUT/f).mkdir(parents=True,exist_ok=True)
 source=PSDImage.open(SOURCE);lookup={l.name:l for l in pixels(source)};original={s:full(lookup[f'SmallTwinTail_{s}_RootCompleted_LOCAL']) for s in ['L','R']};boundary=full(lookup['SmallTwinTail_R_Boundary_REVIEW'])
 # Front-layer coverage used solely to limit concealed padding.
 targets=[f'SmallTwinTail_{s}_RootCompleted_LOCAL' for s in ['L','R']]+['SmallTwinTail_R_Boundary_REVIEW']
 for n in targets:lookup[n].visible=False
 cover=np.array(source.composite(force=True))[:,:,3]
 for n in targets:lookup[n].visible=True
 yy,xx=np.indices((2048,2048));parts={};records=[];edit=np.zeros((2048,2048),bool)
 for s,old in original.items():
  old[old[:,:,3]==0]=0;rgb=old[:,:,:3].astype('int16');r,g,b=rgb.transpose(2,0,1)
  # Only the visually inspected lower inner regions: blue hair and dark blue contours remain.
  warm=(r-b>-10)&(r-g>0)&(old[:,:,3]>0)
  if s=='L':
   # Trace the front gold lock's brown contour, including mixed edge pixels.
   edge=PchipInterpolator([730,750,780,820,860,900,940,970,1000],[433,428,423,416,414,416,425,437,455],extrapolate=True)(yy[:,0])[:,None]
   remove=(yy>=730)&((xx>=edge)|(warm&(xx>=410)))&(old[:,:,3]>0)
  else:remove=warm&(yy>=830)
  clean=old.copy();clean[remove]=0;context=old.copy();context[~remove]=0;recovered=np.zeros_like(old)
  if s=='R':
   br,bg,bb=boundary[:,:,:3].astype('int16').transpose(2,0,1)
   foreground=((yy>=830)&(br-bb>-10)&(br-bg>0))|((yy<510)&(br-bg>40)&(bb-bg>5))
   recovered=boundary.copy();recovered[foreground]=0;recovered[recovered[:,:,3]==0]=0
   rest=boundary.copy();rest[~foreground]=0;rest[rest[:,:,3]==0]=0
   clean=over(clean,recovered);context=over(context,rest)
  # Narrow concealed inward margin, colour from the same side's nearby hair interior.
  alpha=clean[:,:,3];opaque=alpha>=250;dist,nearest=distance_transform_edt(~opaque,return_indices=True)
  inward=(xx>=nearest[1]) if s=='L' else (xx<=nearest[1])
  taper=np.sin(np.pi*np.clip((yy-510)/430,0,1))**2
  local_cover=np.maximum(cover,context[:,:,3]) if s=='L' else cover
  support=(alpha==0)&(dist<=24*taper)&(dist>0)&inward&(local_cover>=250)
  if s=='R':support&=yy<850
  interior=cv2.erode(opaque.astype('uint8'),np.ones((7,7),np.uint8))>0
  # Exclude dark outlines from the colour donor mask.
  interior&=clean[:,:,:3].mean(axis=2)>140
  _,near=distance_transform_edt(~interior,return_indices=True)
  backing=np.zeros_like(old);backing[support,:3]=clean[near[0][support],near[1][support],:3];backing[support,3]=255
  complete=over(backing,clean);complete[complete[:,:,3]==0]=0
  parts[s]={'original':old,'clean':clean,'recovered':recovered,'context':context,'backing':backing,'complete':complete}
  for k,a in parts[s].items():Image.fromarray(a).save(OUT/'layers'/f'SmallTwinTail_{s}_{k}.png')
  Image.fromarray((remove*255).astype('uint8')).save(OUT/'masks'/f'{s}-context-selection.png');Image.fromarray((support*255).astype('uint8')).save(OUT/'masks'/f'{s}-concealed-padding.png')
  edit|=support|remove|(boundary[:,:,3]>0 if s=='R' else False)
  records.append({'side':s,'context_pixels_from_main':int(remove.sum()),'source_inner_hair_recovered_pixels':int((recovered[:,:,3]>0).sum()),'concealed_padding_pixels':int(support.sum()),'max_padding_native_pixels':24,'padding_restricted_to_front_coverage':True,'changed_main_pixels_outside_warm_context':int(np.any(clean[~remove]!=old[~remove],axis=1).sum()) if s=='L' else 'right includes recovered boundary'})
 psd=PSDImage.new('RGBA',(2048,2048),color=0);clone(source,psd,psd,[]);dest={l.name:l for l in pixels(psd)};expected={}
 for s,a in parts.items():
  old=dest[f'SmallTwinTail_{s}_RootCompleted_LOCAL'];parent=old.parent;index=list(parent).index(old)
  for key,label in [('complete',f'SmallTwinTail_{s}_InnerRepaired_LOCAL'),('context',f'SmallTwinTail_{s}_ForegroundContext_PRESERVED')]:
   arr=a[key];new=add(psd,parent,Image.fromarray(arr),label);parent.remove(new);parent.insert(index,new);index+=1;expected[label]=arr
  old.visible=False
 dest['SmallTwinTail_R_Boundary_REVIEW'].visible=False
 path=OUT/'Rurino_SmallTwinTail_Inner_v034.psd';psd.save(path);saved=PSDImage.open(path);after={l.name:l for l in pixels(saved)}
 for n,old in lookup.items():
  new=after[n];assert old.offset==new.offset and np.array_equal(np.array(old.topil()),np.array(new.topil())),n
  assert (old.opacity,old.blend_mode,old.clipping_layer)==(new.opacity,new.blend_mode,new.clipping_layer),n
  assert new.visible==(False if n in targets else old.visible),n
 for n,a in expected.items():assert np.array_equal(full(after[n]),a),n
 states=[]
 for state in ['Open','Half','Closed']:
  for doc in [source,saved]:
   for group in doc:
    if group.name.startswith('02_'):group.visible=group.name=='02_'+state
  before=np.array(source.composite(force=True));actual=np.array(saved.composite(force=True));delta=np.abs(actual.astype('int16')-before.astype('int16'));assert not delta[~edit].any(),state
  assert not ((before[:,:,3]==0)&(actual[:,:,3]>0)).any(),state
  assert delta.max()<=16,(state,int(delta.max()))
  states.append({'state':state,'outside_edit_mask_exact':True,'changed_pixels':int(np.any(delta,axis=2).sum()),'max_channel_difference':int(delta.max()),'new_pixels_outside_previous_silhouette':0})
  if state=='Open':Image.fromarray(actual).save(OUT/'qa/saved-psd-open.png')
 previews(parts)
 report={'input_psd_sha256':sha(SOURCE),'saved_psd_sha256':sha(path),'pixel_layers':len(after),'original_81_layers_retained':True,'new_layers_match_pngs':True,'brows_fringe_and_root_work_retained':True,'parts':records,'states':states,'method':'source-pixel ownership cleanup, recovery of existing right inner hair, limited concealed padding','limitations':['warm context selection may still leave mixed antialiased edges','small-tail interior and full concealed surfaces not finished','padding is limited; no motion or physics acceptance','left historical boundary context remains separately retained','large tails and old outer dirt still pending'],'libtv_generation_used':False}
 (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
