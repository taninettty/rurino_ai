"""Complete small-tail flower-occluded roots using local raster painting.
No new generated image or rig. Preserve originals and flower-edge context.
"""
import json
import cv2,numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import distance_transform_edt,gaussian_filter1d
from PIL import Image,ImageDraw,ImageFont
from psd_tools import PSDImage
from split_left_head_parts_v34 import TURN,pixels,clone,add,sha
from build_hair_flow_redraw_v34 import full
from complete_fringe_materials_v34 import checker,FONT
SOURCE=TURN/'fringe_material_completion/Rurino_Fringe_SourceRestored_v034.psd'
OUT=TURN/'smalltail_root_completion'
# Native 2048 coordinates, independently traced roots behind the flower ties.
CONFIG={
'L':{'y':[210,240,320,400,480,550,590], 'left':[505,480,440,410,380,360,345], 'right':[525,550,530,505,477,452,443], 'sample_y':(505,535),'sample_x':(395,455)},
'R':{'y':[200,240,320,400,480,540,590], 'left':[1510,1490,1475,1480,1495,1510,1520], 'right':[1540,1595,1640,1675,1705,1735,1760], 'sample_y':(520,550),'sample_x':(1535,1695)},
}

def preview(outputs):
 sheet=Image.new('RGB',(1440,1220),'#e8edf3');d=ImageDraw.Draw(sheet);font=ImageFont.truetype(FONT,21)
 for row,s in enumerate(['L','R']):
  union=np.maximum(outputs[s]['original'][:,:,3],outputs[s]['complete'][:,:,3]);b=Image.fromarray(union).getbbox();b=(b[0]-10,b[1]-10,b[2]+10,b[3]+10)
  for col,(k,title) in enumerate([('original','修补前'),('complete','补根后 · 实际透明层'),('context','移出的花瓣残片')]):
   x=col*480;y=row*590;tile=checker((460,510));im=Image.fromarray(outputs[s][k]).crop(b);im.thumbnail((445,500));tile.paste(im,((460-im.width)//2,(510-im.height)//2),im);sheet.paste(tile,(x+10,y+48));d.text((x+12,y+12),s+' · '+title,font=font,fill='#26394c')
 d.text((16,1180),'局部绘制遮挡发根；可见发梢保留。不是完整隐藏面或运动验收。',font=font,fill='#52647a')
 sheet.save(OUT/'qa/smalltail-roots-comparison.jpg',quality=97)

def prepare(source):
 lookup={l.name:l for l in pixels(source)}
 # Actual front coverage, not assumed from the hand-drawn root window.
 for s in CONFIG:
  lookup[f'SmallTwinTail_{s}_Visible'].visible=False
  lookup[f'SmallTwinTail_{s}_Boundary_REVIEW'].visible=False
 cover=np.array(source.composite(force=True))[:,:,3]
 for s in CONFIG:
  lookup[f'SmallTwinTail_{s}_Visible'].visible=True
  lookup[f'SmallTwinTail_{s}_Boundary_REVIEW'].visible=True
 yy,xx=np.indices((2048,2048));outputs={};records=[]
 for s,cfg in CONFIG.items():
  old=full(lookup[f'SmallTwinTail_{s}_Visible']);old[old[:,:,3]==0]=0
  rgb=old[:,:,:3].astype('int16');r,g,b=rgb.transpose(2,0,1)
  # Saturated pink fragments in the golden root are flower remnants, not hair shadow.
  flower=(old[:,:,3]>0)&(yy<510)&(r-g>45)&(b-g>7)&(g<170)
  flower=(cv2.dilate(flower.astype('uint8'),np.ones((3,3),np.uint8))>0)&((old[:,:,3]>=250)|(cover>=250))
  context=old.copy();context[~flower]=0
  clean=old.copy();clean[flower]=0
  left=PchipInterpolator(cfg['y'],cfg['left'],extrapolate=False)(yy[:,0]);right=PchipInterpolator(cfg['y'],cfg['right'],extrapolate=False)(yy[:,0]);active=np.isfinite(left)
  left=np.nan_to_num(left)[:,None];right=np.nan_to_num(right)[:,None];u=np.clip((xx-left)/np.maximum(right-left,1),0,1)
  shape=active[:,None]&(xx>=left)&(xx<=right)
  # Own-side transverse palette; no mirrored pixels or copied face/flower paint.
  y0,y1=cfg['sample_y'];x0,x1=cfg['sample_x'];patch=clean[y0:y1,x0:x1];assert (patch[:,:,3]>250).mean()>.9
  profile=gaussian_filter1d(np.median(patch[:,:,:3],axis=0),3,axis=0)
  color=np.stack([np.interp(u,np.linspace(0,1,len(profile)),profile[:,k]) for k in range(3)],axis=2)
  # Replace old artificial diagonal root lines only where front artwork nearly opaquely covers them.
  replace=shape&(cover>=250)&(yy<510)
  missing=shape&(clean[:,:,3]<255)&((cover>=250)|flower)
  support=replace|missing|flower
  # Retain actual outer contour; keep local paint away from exposed source edges.
  known=(clean[:,:,3]>=250)&~replace&(clean[:,:,:3].mean(axis=2)>185)
  interior=cv2.erode(known.astype('uint8'),np.ones((5,5),np.uint8))>0
  dist,near=distance_transform_edt(~interior,return_indices=True)
  adjacent=clean[near[0],near[1],:3].astype('float32');t=np.clip(dist/28,0,1);blend=(1-t*t*(3-2*t))[:,:,None]
  color=color*(1-blend)+adjacent*blend
  paint=np.zeros_like(old);paint[support,:3]=np.rint(color[support]).clip(0,255).astype('uint8');paint[support,3]=255
  complete=clean.copy();complete[support]=paint[support];complete[complete[:,:,3]==0]=0
  for k,a in {'original':old,'clean':clean,'complete':complete,'context':context,'paint':paint}.items():Image.fromarray(a).save(OUT/'layers'/f'SmallTwinTail_{s}_{k}.png')
  Image.fromarray((support*255).astype('uint8')).save(OUT/'masks'/f'{s}-paint-support.png')
  outputs[s]={'original':old,'clean':clean,'complete':complete,'context':context,'paint':paint}
  records.append({'side':s,'painted_pixels':int(support.sum()),'added_alpha_pixels':int(((complete[:,:,3]>0)&(old[:,:,3]==0)).sum()),'flower_context_pixels':int((context[:,:,3]>0).sum()),'below_row_590_exact':bool(np.array_equal(old[591:],complete[591:])),'root_geometry_native':cfg})
 return outputs,records

def main():
 for f in ['layers','masks','qa']:(OUT/f).mkdir(parents=True,exist_ok=True)
 source=PSDImage.open(SOURCE);outputs,records=prepare(source);lookup={l.name:l for l in pixels(source)}
 psd=PSDImage.new('RGBA',(2048,2048),color=0);clone(source,psd,psd,[]);dest={l.name:l for l in pixels(psd)};expected={};hidden=[];edit=np.zeros((2048,2048),bool)
 for s in CONFIG:
  name=f'SmallTwinTail_{s}_Visible';old=dest[name];parent=old.parent;index=list(parent).index(old)
  for k,label in [('complete',f'SmallTwinTail_{s}_RootCompleted_LOCAL'),('context',f'SmallTwinTail_{s}_FlowerContext_PRESERVED')]:
   arr=outputs[s][k];new=add(psd,parent,Image.fromarray(arr),label);parent.remove(new);parent.insert(index,new);index+=1;expected[label]=arr
  old.visible=False;hidden.append(name);edit|=(outputs[s]['paint'][:,:,3]>0)|(outputs[s]['context'][:,:,3]>0)
 path=OUT/'Rurino_SmallTwinTail_Roots_v034.psd';psd.save(path);saved=PSDImage.open(path);after={l.name:l for l in pixels(saved)}
 for n,old in lookup.items():
  new=after[n];assert old.offset==new.offset and np.array_equal(np.array(old.topil()),np.array(new.topil())),n
  assert (old.opacity,old.blend_mode,old.clipping_layer)==(new.opacity,new.blend_mode,new.clipping_layer),n
  assert new.visible==(False if n in hidden else old.visible),n
 for n,arr in expected.items():assert np.array_equal(full(after[n]),arr),n
 states=[]
 for state in ['Open','Half','Closed']:
  for doc in [source,saved]:
   for group in doc:
    if group.name.startswith('02_'):group.visible=group.name=='02_'+state
  before=np.array(source.composite(force=True));actual=np.array(saved.composite(force=True));diff=np.abs(actual.astype('int16')-before.astype('int16'));assert not diff[~edit].any(),state
  outside=int(((before[:,:,3]==0)&(actual[:,:,3]>0)).sum());assert outside==0,(state,outside)
  assert diff.max()<=16,(state,int(diff.max()))
  states.append({'state':state,'outside_edit_mask_exact':True,'changed_pixels':int(np.any(diff,axis=2).sum()),'max_channel_difference':int(diff.max()),'new_pixels_outside_head':outside})
  if state=='Open':Image.fromarray(actual).save(OUT/'qa/saved-psd-open.png')
 preview(outputs)
 report={'input_psd_sha256':sha(SOURCE),'saved_psd_sha256':sha(path),'pixel_layers':len(after),'original_77_layers_retained':True,'new_layers_match_pngs':True,'independent_brows_and_fringe_retained':True,'parts':records,'states':states,'method':'local raster painting of flower-occluded small-tail roots using own-side hair palette; saturated flower fragments preserved separately','limitations':['root geometry is local reconstruction, not recovered unseen original art','not complete interior shaft or head-angle materials','no movement mesh or physics verification','large twin tails and boundary-review dirt remain pending'],'libtv_generation_used':False}
 (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
