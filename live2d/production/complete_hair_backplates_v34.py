"""Paint concealed hair continuations from each component's own colour profiles.
Backings sit below the existing art. Existing 85 pixel layers are unchanged.
These are local reconstructed materials, not new generated art or a motion rig.
"""
import argparse,json
import cv2,numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import distance_transform_edt,gaussian_filter1d
from PIL import Image,ImageDraw,ImageFont
from psd_tools import PSDImage
from psd_tools.api.layers import Group
from split_left_head_parts_v34 import TURN,pixels,clone,add,sha
from build_hair_flow_redraw_v34 import full
from complete_fringe_materials_v34 import checker,FONT
SOURCE=TURN/'smalltail_inner_refinement/Rurino_SmallTwinTail_Inner_v034.psd'
OUT=TURN/'hair_concealed_completion'
CONFIG={
 'Large_L':{'source':'LargeTwinTail_L_Visible','label':'左大马尾','y':[330,500,750,1000,1200,1400,1600,1800,2048], 'left':[550,485,440,425,350,245,95,-70,-200],'right':[570,630,690,730,740,650,480,330,240],'sample':(1290,1310,355,740),'tip_sample':(1840,1860,12,245),'scope':'reconstructed tie-to-shoulder root and body-occluded long hair; bottom remains canvas-cropped'},
 'Large_R':{'source':'LargeTwinTail_R_Visible','label':'右大马尾','y':[330,500,750,1000,1200,1400,1600,1800,2048], 'left':[1450,1380,1330,1290,1250,1270,1440,1610,1780],'right':[1470,1540,1600,1660,1720,1830,1970,2120,2250],'sample':(1290,1310,1445,1735),'tip_sample':(1840,1860,1800,2000),'scope':'reconstructed tie-to-shoulder root and body-occluded long hair; bottom remains canvas-cropped'},
 'Small_L':{'source':'SmallTwinTail_L_InnerRepaired_LOCAL','label':'左小马尾内缘','y':[450,550,650,750,850,950], 'left':[420,365,330,340,370,400],'right':[505,475,455,450,445,435],'sample':(510,530,395,450),'scope':'concealed inward continuity behind front gold lock; existing blue tips retained'},
 'Small_R':{'source':'SmallTwinTail_R_InnerRepaired_LOCAL','label':'右小马尾内缘','y':[450,500,600,700,800,890], 'left':[1480,1450,1425,1435,1460,1500],'right':[1510,1530,1555,1575,1560,1510],'sample':(510,530,1500,1580),'scope':'bridge remaining inner notches, retaining existing blue tips'},
 'Cheek_L':{'source':'CheekLock_ImageLeft','label':'左贴脸发根','y':[150,190,250,350,450], 'left':[790,710,625,550,520],'right':[798,755,715,650,600],'sample':(350,365,582,628),'scope':'short concealed continuation into shared crown/fringe, not a full replacement lock'},
 'Cheek_R':{'source':'CheekLock_ImageRight','label':'右贴脸发根','y':[110,150,250,350,450], 'left':[1040,1090,1160,1210,1250],'right':[1045,1145,1270,1325,1365],'sample':(440,460,1265,1340),'scope':'short concealed continuation into shared crown/fringe'},
 'Temple_R':{'source':'TempleLock_ImageRight','label':'右鬓发根','y':[120,180,300,450], 'left':[1140,1180,1255,1325],'right':[1145,1250,1370,1450],'sample':(350,365,1325,1385),'scope':'concealed upper connection only; junction ownership remains reviewable'},
 'Thin_R':{'source':'LongFrontLock_ImageRight','label':'右侧细长前发根','y':[760,850,950,1050,1150], 'left':[1420,1400,1380,1380,1400],'right':[1428,1465,1475,1475,1480],'sample':(1090,1110,1395,1460),'scope':'concealed upper shaft behind short hair; not an additional ponytail'},
}

def profile(a,box):
 y0,y1,x0,x1=box;patch=a[y0:y1,x0:x1];valid=patch[:,:,3]>=250
 values=np.where(valid[:,:,None],patch[:,:,:3].astype('float32'),np.nan)
 with np.errstate(invalid='ignore'):
  import warnings
  with warnings.catch_warnings():warnings.simplefilter('ignore',RuntimeWarning);p=np.nanmedian(values,axis=0)
 for k in range(3):
  hit=np.isfinite(p[:,k]);assert hit.sum()>10,box;p[:,k]=np.interp(np.arange(len(p)),np.flatnonzero(hit),p[hit,k])
 return gaussian_filter1d(p,10,axis=0)

def combine(a,b):return np.array(Image.alpha_composite(Image.fromarray(a),Image.fromarray(b)))

def previews(parts):
 # Equal scale/viewport before and after for every component.
 sheet=Image.new('RGB',(1440,len(parts)*510+55),'#e8edf3');d=ImageDraw.Draw(sheet);font=ImageFont.truetype(FONT,21)
 for row,(key,a) in enumerate(parts.items()):
  box=Image.fromarray(np.maximum(a['original'][:,:,3],a['complete'][:,:,3])).getbbox();box=(box[0]-8,box[1]-8,box[2]+8,box[3]+8)
  for col,(k,label) in enumerate([('original','原独立素材'),('complete','补全检查素材'),('backing','本轮隐藏补画')]):
   x=col*480;y=row*510;tile=checker((460,440));im=Image.fromarray(a[k]).crop(box);im.thumbnail((445,425));tile.paste(im,((460-im.width)//2,(440-im.height)//2),im);sheet.paste(tile,(x+10,y+48));d.text((x+10,y+12),CONFIG[key]['label']+' · '+label,font=font,fill='#26394c')
 d.text((15,len(parts)*510+10),'中列为完整轮廓检查稿，PSD 中默认隐藏；安全遮挡补层另存。长发仍被画布裁切，未做运动验收。',font=font,fill='#52647a')
 sheet.save(OUT/'qa/hair-completion-all.jpg',quality=96)
 sheet.crop((0,0,1440,1020)).save(OUT/'qa/large-tail-completion.jpg',quality=97)
 sheet.crop((0,1020,1440,2040)).save(OUT/'qa/small-tail-junction.jpg',quality=97)
 sheet.crop((0,2040,1440,len(parts)*510)).save(OUT/'qa/front-hair-roots.jpg',quality=96)

def protected_face_mask(source):
 mask=np.zeros((2048,2048),bool)
 names={'FacePaint_Visible_NOT_FEATURE_SPLIT_BrowRemoved_LOCAL','Ear_Near_ImageRight','Neck_Visible','Eyebrow_L_Full_LOCAL_CLEANUP','Eyebrow_R_Full_LOCAL_CLEANUP'}
 for layer in pixels(source):
  if layer.name in names:mask|=full(layer)[:,:,3]>0
 for group in source:
  if group.name.startswith('02_'):
   for layer in pixels(group):mask|=full(layer)[:,:,3]>0
 return mask

def prepare(source):
 lookup={l.name:l for l in pixels(source)};base=np.array(source.composite(force=True));coverage=base[:,:,3];face_mask=protected_face_mask(source);yy,xx=np.indices((2048,2048));parts={};records=[]
 for key,cfg in CONFIG.items():
  a=full(lookup[cfg['source']]);a[a[:,:,3]==0]=0
  left=PchipInterpolator(cfg['y'],cfg['left'],extrapolate=False)(yy[:,0]);right=PchipInterpolator(cfg['y'],cfg['right'],extrapolate=False)(yy[:,0]);active=np.isfinite(left)
  left=np.nan_to_num(left)[:,None];right=np.nan_to_num(right)[:,None];width=np.maximum(right-left,1);u=np.clip((xx-left)/width,0,1)
  edge=np.clip(np.minimum(xx-left+.5,right-xx+.5),0,1)*active[:,None]
  support=(edge>0)&(a[:,:,3]<250)
  pal=profile(a,cfg['sample']);colour=np.stack([np.interp(u,np.linspace(0,1,len(pal)),pal[:,k]) for k in range(3)],axis=2)
  if 'tip_sample' in cfg:
   tip=profile(a,cfg['tip_sample']);low=np.stack([np.interp(u,np.linspace(0,1,len(tip)),tip[:,k]) for k in range(3)],axis=2);t=np.clip((yy-1400)/550,0,1)[:,:,None];t=t*t*(3-2*t);colour=colour*(1-t)+low*t
  # Bridge to the adjacent same-side interior. Do not copy the dark contour into new paint.
  interior=cv2.erode((a[:,:,3]>=250).astype('uint8'),np.ones((9,9),np.uint8))>0
  interior&=a[:,:,:3].mean(axis=2)>140
  # Smooth local colour continuation rather than copying the nearest dark edge.
  dist=distance_transform_edt(~interior);weight=cv2.GaussianBlur(interior.astype('float32'),(0,0),18)
  average=np.stack([cv2.GaussianBlur(a[:,:,k].astype('float32')*interior,(0,0),18)/np.maximum(weight,1e-6) for k in range(3)],axis=2)
  t=np.clip(dist/85,0,1);blend=((1-t*t*(3-2*t))*(weight>.0001))[:,:,None];colour=colour*(1-blend)+average*blend
  backing=np.zeros_like(a);backing[support,:3]=np.rint(colour[support]).clip(0,255).astype('uint8');backing[support,3]=np.rint(edge[support]*255).astype('uint8');backing[backing[:,:,3]==0]=0
  safe=backing.copy();safe[(coverage<250)|face_mask]=0
  complete=combine(backing,a);complete[complete[:,:,3]==0]=0
  seam=np.zeros((2048,2048),bool)
  if key.startswith('Large_'):
   # Occlusion cuts carry pieces of face/garment outline. In the hidden review
   # material only, soften those internal dark/white cut pixels; the original
   # PSD artwork and default assembly remain untouched.
   source_inside=cv2.distanceTransform((a[:,:,3]>=250).astype('uint8'),cv2.DIST_L2,5)
   new_inside=cv2.distanceTransform((complete[:,:,3]>=250).astype('uint8'),cv2.DIST_L2,5)
   rgb=a[:,:,:3].astype('float32');dark=rgb.mean(axis=2)<170;white=rgb.min(axis=2)>240
   seam=(source_inside>0)&(source_inside<8)&(new_inside>14)&(edge>0)&(dark|white)&(yy>980)&(yy<1480)
   complete[seam,:3]=np.rint(colour[seam]).clip(0,255).astype('uint8')
  assert np.array_equal(complete[(a[:,:,3]==255)&~seam],a[(a[:,:,3]==255)&~seam])
  parts[key]={'original':a,'backing':backing,'safe':safe,'complete':complete}
  Image.fromarray((seam*255).astype('uint8')).save(OUT/'masks'/f'{key}_candidate_seam_repair.png')
  for k,b in parts[key].items():Image.fromarray(b).save(OUT/'layers'/f'{key}_{k}.png')
  Image.fromarray((support*255).astype('uint8')).save(OUT/'masks'/f'{key}_support.png')
  records.append({'key':key,'source_layer':cfg['source'],'label':cfg['label'],'scope':cfg['scope'],'painted_pixels':int((backing[:,:,3]>0).sum()),'added_alpha_pixels':int(((complete[:,:,3]>0)&(a[:,:,3]==0)).sum()),'default_safe_backing_pixels':int((safe[:,:,3]>0).sum()),'unoccluded_candidate_pixels':int(((backing[:,:,3]>0)&(coverage<250)).sum()),'opaque_source_pixels_outside_candidate_seam_mask_preserved':True,'candidate_seam_repair_pixels':int(seam.sum()),'geometry_and_palette':cfg})
 previews(parts);(OUT/'preparation.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n');return parts,records

def main(prepare_only=False):
 for f in ['layers','masks','qa']:(OUT/f).mkdir(parents=True,exist_ok=True)
 source=PSDImage.open(SOURCE);parts,records=prepare(source)
 if prepare_only:print('Prepared',len(parts),'components for visual inspection');return
 lookup={l.name:l for l in pixels(source)};face_mask=protected_face_mask(source);psd=PSDImage.new('RGBA',(2048,2048),color=0);clone(source,psd,psd,[])
 group=Group.new('06_Hair_Concealed_Backings_LOCAL_NOT_MOTION_APPROVED',parent=psd);psd.remove(group);psd.insert(0,group)
 # Backings are deliberately below all existing art, not pasted over foreground faces or hair.
 for key,a in parts.items():add(psd,group,Image.fromarray(a['safe']),key+'_ConcealedBacking_LOCAL')
 review=Group.new('07_Full_Hair_Materials_REVIEW_OFF',parent=psd);review.visible=False
 for key,a in parts.items():
  g=Group.new(key+'_FullMaterial_REVIEW_OFF',parent=review);g.visible=False;add(psd,g,Image.fromarray(a['complete']),key+'_FullMaterial_LOCAL_REVIEW')
 path=OUT/'Rurino_Hair_Concealed_Backings_v034.psd';psd.save(path);saved=PSDImage.open(path);after={l.name:l for l in pixels(saved)}
 for name,old in lookup.items():
  new=after[name];assert old.offset==new.offset and np.array_equal(np.array(old.topil()),np.array(new.topil())),name
  assert (old.visible,old.opacity,old.blend_mode,old.clipping_layer)==(new.visible,new.opacity,new.blend_mode,new.clipping_layer),name
 for key,a in parts.items():
  assert np.array_equal(full(after[key+'_ConcealedBacking_LOCAL']),a['safe']),key
  assert np.array_equal(full(after[key+'_FullMaterial_LOCAL_REVIEW']),a['complete']),key
 support=np.logical_or.reduce([a['safe'][:,:,3]>0 for a in parts.values()]);states=[]
 for state in ['Open','Half','Closed']:
  for doc in [source,saved]:
   for g in doc:
    if g.name.startswith('02_'):g.visible=g.name=='02_'+state
  before=np.array(source.composite(force=True));actual=np.array(saved.composite(force=True));delta=np.abs(actual.astype('int16')-before.astype('int16'));assert not delta[~support].any(),state
  assert not ((before[:,:,3]==0)&(actual[:,:,3]>0)).any(),state
  assert delta.max()<=16,(state,int(delta.max()))
  assert not delta[face_mask].any(),state
  states.append({'state':state,'outside_backing_mask_exact':True,'changed_pixels':int(np.any(delta,axis=2).sum()),'max_channel_difference':int(delta.max()),'protected_face_eyes_brows_neck_rgba_exact':True,'new_pixels_outside_previous_silhouette':0})
  if state=='Open':Image.fromarray(actual).save(OUT/'qa/saved-psd-open.png')
 report={'input_psd_sha256':sha(SOURCE),'saved_psd_sha256':sha(path),'pixel_layers':len(after),'all_original_85_pixels_and_properties_preserved':True,'saved_backings_match_pngs':True,'backing_group_default_visible':True,'full_material_candidate_group_default_visible':False,'parts':records,'states':states,'placement':'default backings are clipped to original opaque coverage and placed behind art; full merged candidates have smooth untrimmed contours and are in a separate hidden review group','limitations':['concealed paint is reconstructed, not observed original anatomy','long tail ends remain clipped by the 2048 canvas','shared crown and fringe not newly separated or fully reconstructed','forehead/cheek/temple mixed ownership and old contour dirt remain pending','no Cubism binding, continuous turns, body motion or physics validation'],'libtv_generation_used':False}
 (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='parts'},ensure_ascii=False,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--prepare-only',action='store_true');main(p.parse_args().prepare_only)
