"""Reassign neighbouring outline pixels and antialias the R02/R03 split.
Local raster ownership correction, not complete underpainting or a motion rig.
"""
import json
import cv2
import numpy as np
from scipy.interpolate import PchipInterpolator
from PIL import Image,ImageDraw,ImageFont
from psd_tools import PSDImage
from split_left_head_parts_v34 import TURN,pixels,clone,add,sha
from build_hair_flow_redraw_v34 import full
OUT=TURN/'hair_drop_ownership'
SOURCE=TURN/'hair_drop_refinement/Rurino_Left_Head_Drop_Roots_v034.psd'
FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
NAMES=['R02_RootExtended_LOCAL_PAINT','R03_UnderDrop','R01_RootBoundary_Cleaned']
NEW=['R02_InnerEdge_Refined','R03_Outline_Reassigned_VISIBLE_ONLY','R01_RootBoundary_Ownership_Cleaned']

def refine(a,b,pending):
 y=np.arange(2048);xx=np.arange(2048)[None,:]
 ys=[650,690,730,770,810,840,870,900,930,950,965,975]
 xs=[1663,1671,1680,1691,1703,1712,1716,1719,1721,1720,1716,1712]
 edge=PchipInterpolator(ys,xs)(np.clip(y,650,975))
 active=(y[:,None]>=650)&(y[:,None]<=880)
 keep=np.where(active,np.clip(xx-edge[:,None]+.5,0,1),1)
 # Existing partially transparent silhouette pixels must have one owner;
 # duplicating them would increase opacity when composited twice.
 keep=np.where(a[:,:,3]<255,(keep>=.5).astype('float64'),keep)
 new=a.copy();new[:,:,3]=np.rint(a[:,:,3]*keep).astype('uint8');new[new[:,:,3]==0]=0
 # Retain the full source behind the antialiased split, so the pair has no
 # mathematical half-alpha seam. R02 is placed immediately above R03.
 transfer=(keep<1)&(a[:,:,3]>0);plate=np.zeros_like(a);plate[transfer]=a[transfer]
 neighbor=np.array(Image.alpha_composite(Image.fromarray(plate),Image.fromarray(b)))
 right=PchipInterpolator([830,850,870,890,910,930,950,970,990,1005],[1711,1720,1719,1712,1703,1691,1674,1650,1617,1580])(np.clip(y,830,1005))
 claim=(y[:,None]>=830)&(y[:,None]<=1005)&(xx<=right[:,None])&(xx>=1590)&(pending[:,:,3]>0)
 # Recover only R03's outer/right contour. The left contour belongs to
 # the overlap with R04 and must not acquire a loose neighbouring line.
 row_right=np.max(np.where(b[:,:,3]>0,xx,-1),axis=1)
 claim &= (row_right[:,None]>=0)&(xx>row_right[:,None])
 near=cv2.dilate((b[:,:,3]>0).astype('uint8'),np.ones((19,19),np.uint8))>0
 rgb=pending[:,:,:3].astype('int16');claim &= near & ~(rgb[:,:,0]>rgb[:,:,2]+2)
 neighbor[claim]=pending[claim];remaining=pending.copy();remaining[claim]=0
 support=transfer|claim
 return [new,neighbor,remaining],support,{'R02_pixels_reassigned':int(transfer.sum()),'pending_outline_pixels_reassigned':int(claim.sum()),'antialiased_overlap_pixels':int(((keep>0)&(keep<1)&(a[:,:,3]>0)).sum()),'curve_y':ys,'curve_x':xs}

def panel(items,box,path,full_contours=False):
 w=480;h=860;sheet=Image.new('RGB',(w*len(items),h),'#e9eef4');d=ImageDraw.Draw(sheet);font=ImageFont.truetype(FONT,19)
 for i,(title,arr) in enumerate(items):
  d.text((i*w+12,12),title,font=font,fill='#25344a')
  for y in range(50,h-15,20):
   for x in range(i*w+10,(i+1)*w-10,20):d.rectangle((x,y,x+19,y+19),fill='#ced8e3' if (x//20+y//20)%2 else '#e8edf2')
  im=Image.fromarray(arr).crop(box);scale=min(450/im.width,770/im.height);im=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.LANCZOS);sheet.paste(im,(i*w+(w-im.width)//2,65),im)
 sheet.save(path,quality=96)

def main():
 for folder in ['layers','qa','masks']:(OUT/folder).mkdir(parents=True,exist_ok=True)
 source=PSDImage.open(SOURCE);lookup={l.name:l for l in pixels(source)}
 originals=[full(lookup[n]) for n in NAMES];arrays,support,record=refine(*originals)
 for name,arr in zip(NEW,arrays):Image.fromarray(arr).save(OUT/'layers'/(name+'.png'))
 Image.fromarray((support*255).astype('uint8')).save(OUT/'masks/ownership-support.png')
 psd=PSDImage.new('RGBA',(2048,2048),color=0);clone(source,psd,psd,[]);dest={l.name:l for l in pixels(psd)}
 # The old R02/R03 are adjacent active locks. Place R03 below R02, preserving
 # their relationship to the other hair layers; originals stay hidden backups.
 parent=dest[NAMES[0]].parent;index=list(parent).index(dest[NAMES[0]])
 for j in [1,0]:
  layer=add(psd,parent,Image.fromarray(arrays[j]),NEW[j]);parent.remove(layer);parent.insert(index,layer);index+=1
 old=dest[NAMES[2]];parent=old.parent;index=list(parent).index(old)
 layer=add(psd,parent,Image.fromarray(arrays[2]),NEW[2]);parent.remove(layer);parent.insert(index,layer)
 for name in NAMES:dest[name].visible=False
 path=OUT/'Rurino_Left_Head_Hair_Edges_v034.psd';psd.save(path);saved=PSDImage.open(path);after={l.name:l for l in pixels(saved)}
 for n,arr in zip(NEW,arrays):
  assert np.array_equal(full(after[n]),arr),n
 assert len(after)==54 and sum(l.clipping_layer for l in after.values())==4
 for name,old in lookup.items():
  new=after[name];assert old.offset==new.offset and np.array_equal(np.array(old.topil()),np.array(new.topil())),name
  assert (old.opacity,old.blend_mode,old.clipping_layer)==(new.opacity,new.blend_mode,new.clipping_layer),name
  assert new.visible==(False if name in NAMES else old.visible),name
 baseline=np.array(source.composite(force=True));actual=np.array(saved.composite(force=True));delta=np.abs(actual.astype('int16')-baseline.astype('int16'))
 assert not delta[~support].any()
 assert not ((baseline[:,:,3]==0)&(actual[:,:,3]>0)).any()
 assert not ((baseline[:,:,3]==255)&(actual[:,:,3]<255)).any()
 Image.fromarray(actual).save(OUT/'qa/saved-psd-open.png')
 # Read back actual layers, not a composite crop, for contour inspection.
 a,b=[full(after[n]) for n in NEW[:2]]
 box=(1480,200,1800,1030)
 panel([('R02 修前完整图层',originals[0]),('R02 内缘修后',a),('R03 修前 · 可见段',originals[1]),('R03 修后 · 根部仍待补',b)],box,OUT/'qa/actual-edge-layer-comparison.jpg')
 panel([('局部放大：修前',originals[0]),('局部放大：R02 修后',a),('局部放大：R03 修后',b)],(1580,620,1790,1010),OUT/'qa/edge-detail-comparison.jpg')
 panel([('头部合成：修前',baseline),('头部合成：修后',actual)],(120,0,1960,1800),OUT/'qa/edge-head-comparison.jpg')
 checks=[]
 for state in ['Open','Half','Closed']:
  for doc in [source,saved]:
   for g in doc:
    if g.name.startswith('02_'):g.visible=g.name=='02_'+state
  before=np.array(source.composite(force=True));now=np.array(saved.composite(force=True));assert np.array_equal(before[400:1230,620:1250],now[400:1230,620:1250])
  checks.append({'state':state,'central_face_rgba_exact':True})
 record.update({'input_psd_sha256':sha(SOURCE),'saved_psd_sha256':sha(path),'pixel_layers':54,'original_51_layers_preserved':True,'original_layers_newly_hidden':NAMES,'changed_composite_pixels':int(np.any(delta,axis=2).sum()),'max_composite_channel_difference':int(delta.max()),'changed_pixels_outside_support':0,'new_exterior_pixels':0,'previous_opaque_pixels_becoming_transparent':0,'face_checks':checks,'limitations':['R03 hidden root still incomplete','no motion underlap added; semi-transparent boundary pixels retain a single owner','other locks, motion range and Cubism binding are unfinished'],'method':'local outline ownership reassignment; no new LibTV generation'})
 (OUT/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n');print(json.dumps(record,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
