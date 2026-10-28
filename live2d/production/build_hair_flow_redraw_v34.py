"""Clean and place two independently redrawn LibTV locks; create a review PSD.

Only the new isolated locks receive similarity transforms. The head source is
never warped. Trial placement and complete redrawing are distinct deliverables.
"""
from pathlib import Path
import json,hashlib
import cv2,numpy as np
from scipy.optimize import differential_evolution
from PIL import Image,ImageDraw,ImageFont
from psd_tools import PSDImage
from psd_tools.api.layers import Group
from split_left_head_parts_v34 import ROOT,TURN,pixels,clone,add,sha
OUT=TURN/'hair_flow_redraw';SOURCE=TURN/'left_hair_strands/Rurino_Left_Head_Hair_Strands_v034.psd'
FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'

def full(l):
 im=Image.new('RGBA',(2048,2048));im.paste(l.topil().convert('RGBA'),l.offset);return np.array(im)
def dump(p,o):p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n')
def clean(im):
 a=np.array(im);n,lab,stats,_=cv2.connectedComponentsWithStats((a[:,:,3]>16).astype('uint8'));k=1+int(np.argmax(stats[1:,cv2.CC_STAT_AREA]));keep=cv2.dilate((lab==k).astype('uint8'),np.ones((9,9),np.uint8))>0
 out=a.copy();out[~keep]=0
 return out,int(((a[:,:,3]>0)&~keep).sum())
def tip(a,right):
 y,x=np.where(a[:,:,3]>128);edge=int(x.max() if right else x.min());sel=(x>=edge-3) if right else (x<=edge+3);return np.array([edge,float(np.median(y[sel]))])
def place_matrix(parameters,source_tip,target_tip):
 scale,angle,dx,dy=parameters;t=np.radians(angle);r=scale*np.array([[np.cos(t),-np.sin(t)],[np.sin(t),np.cos(t)]])
 return np.column_stack([r,target_tip+np.array([dx,dy])-r@source_tip])
def warp(a,m):
 # Warp premultiplied color so transparent hidden RGB cannot create dark rims.
 f=a.astype('float32')/255;alpha=f[:,:,3];rgb=f[:,:,:3]*alpha[:,:,None];ap=cv2.warpAffine(alpha,m,(2048,2048),flags=cv2.INTER_CUBIC);premult=cv2.warpAffine(rgb,m,(2048,2048),flags=cv2.INTER_CUBIC);ap=np.clip(ap,0,1);out=np.zeros_like(a);out[:,:,:3]=np.clip(np.rint(premult/np.maximum(ap[:,:,None],1e-6)*255),0,255).astype('uint8');out[:,:,3]=np.rint(ap*255).astype('uint8');out[ap<1/255]=0;return out

def main():
 for n in ['layers','qa']:(OUT/n).mkdir(exist_ok=True)
 src=PSDImage.open(SOURCE);lookup={l.name:l for l in pixels(src)};baseline=np.array(Image.open(TURN/'left_hair_strands/qa/saved-psd-open.png').convert('RGBA'))
 originals={name:full(lookup[name+'_OuterFlick']) for name in ['R01','L01']};cleaned={};placed={};records=[]
 for name in ['R01','L01']:
  p=OUT/'sources'/f'{name.lower()}-flow-redraw-source.png';raw=Image.open(p).convert('RGBA');delivery=json.loads((OUT/'sources'/f'{name.lower()}-delivery.json').read_text())['files'][0];assert p.stat().st_size==delivery['sizeBytes'];assert raw.size==(2048,2048)
  a,removed=clean(raw);cleaned[name]=a;Image.fromarray(a).save(OUT/'layers'/f'{name}_Complete_Redraw_Native.png')
  st=tip(a,name=='R01');tt=tip(originals[name],name=='R01');small=cv2.resize(a[:,:,3],(512,512),interpolation=cv2.INTER_AREA)
  target=cv2.resize(originals[name][:,:,3],(512,512),interpolation=cv2.INTER_AREA)>64
  occ=(cv2.resize(baseline[:,:,3],(512,512),interpolation=cv2.INTER_AREA)>64)&~target;norm=max(target.sum(),1)
  def loss(v):
   m=place_matrix(v,st,tt);m[:,2]/=4;candidate=cv2.warpAffine(small,m,(512,512),flags=cv2.INTER_LINEAR)>64;visible=candidate&~occ
   return (5*np.count_nonzero(target&~visible)+np.count_nonzero(visible&~target))/norm
  fit=differential_evolution(loss,[(.35,1.3),(-30,30),(-12,12),(-12,12)],seed=11,popsize=9,maxiter=45,polish=False,tol=.0005)
  m=place_matrix(fit.x,st,tt);aligned=warp(a,m);placed[name]=aligned;Image.fromarray(aligned).save(OUT/'layers'/f'{name}_Complete_Redraw_Placed.png')
  target_full=originals[name][:,:,3]>128;covered=(aligned[:,:,3]>128)&target_full;missing=target_full&~covered
  records.append({'name':name,'source_file':str(p.relative_to(ROOT)),'source_sha256':sha(p),'source_bytes':p.stat().st_size,'removed_remote_alpha_speck_pixels':removed,'generated_canvas':[2048,2048],'source_tip':st.tolist(),'target_tip':tt.tolist(),'similarity_transform_parameters':dict(zip(['uniform_scale','rotation_degrees','tip_dx','tip_dy'],map(float,fit.x))),'matrix_native':m.tolist(),'old_visible_opaque_pixels':int(target_full.sum()),'old_visible_covered_pixels':int(covered.sum()),'old_visible_uncovered_pixels':int(missing.sum()),'registration_scope':'trial similarity placement of new lock only; not a warp of the head or continuous motion'})
 psd=PSDImage.new('RGBA',(2048,2048),color=0);g=Group.new('00_Complete_Redrawn_Locks_TRIAL',parent=psd)
 for name,a in placed.items():add(psd,g,Image.fromarray(a),name+'_Complete_Redraw')
 preserved=[];clone(src,psd,psd,preserved)
 for l in pixels(psd):
  if l.name in ['R01_OuterFlick','L01_OuterFlick']:l.visible=False
 path=OUT/'Rurino_Left_Head_Two_Redrawn_Locks_TRIAL_v034.psd';psd.save(path);saved=PSDImage.open(path);actual=np.array(saved.composite(force=True));Image.fromarray(actual).save(OUT/'qa/two-locks-head-trial.png')
 slookup={l.name:l for l in pixels(saved)}
 for name,l in lookup.items():
  other=slookup[name];assert other.offset==l.offset and np.array_equal(np.array(other.topil()),np.array(l.topil())),name
  assert (other.opacity,other.blend_mode,other.clipping_layer)==(l.opacity,l.blend_mode,l.clipping_layer),name
  assert other.visible==(False if name in ['R01_OuterFlick','L01_OuterFlick'] else l.visible),name
 assert len(slookup)==46 and sum(l.clipping_layer for l in slookup.values())==4
 # Central face and eyes are outside the replacement regions.
 region=np.zeros((2048,2048),bool);region[400:1230,620:1250]=True;region&=baseline[:,:,3]==255
 delta=np.abs(actual.astype('int16')-baseline.astype('int16'));assert not delta[region].any()
 # Use identical viewport and scale for old/new comparisons, so extent changes
 # stay visible. Complete-lock sheets use separately labeled display scales.
 f=ImageFont.truetype(FONT,23);sheet=Image.new('RGB',(1400,800),'#e6edf4');d=ImageDraw.Draw(sheet)
 for i,(title,a) in enumerate([('原头部',baseline),('两缕重绘放回头部 · 检查稿',actual)]):
  tile=Image.fromarray(a).crop((120,0,1960,1800));tile.thumbnail((690,740));sheet.paste(tile,(i*700+(700-tile.width)//2,50),tile);d.text((i*700+16,12),title,font=f,fill='#29394e')
 sheet.save(OUT/'qa/head-redraw-comparison.jpg',quality=95)
 sheet=Image.new('RGB',(1400,1040),'#e6edf4');d=ImageDraw.Draw(sheet)
 for row,name in enumerate(['R01','L01']):
  for col,(label,a) in enumerate([('原来裁出的可见段',originals[name]),('按发流重画的完整一缕',cleaned[name])]):
   im=Image.fromarray(a);box=im.getbbox();tile=im.crop(box);tile.thumbnail((630,420));x=col*700;y=row*500;sheet.paste(tile,(x+(700-tile.width)//2,y+60),tile);d.text((x+18,y+12),name+' · '+label,font=f,fill='#29394e')
 d.text((718,1004),'各格独立放大；实际放回位置见头部对照',font=ImageFont.truetype(FONT,17),fill='#53637c');sheet.save(OUT/'qa/cut-vs-flow-redraw.jpg',quality=95)
 state_checks=[]
 for state in ['Open','Half','Closed']:
  for p in [src,saved]:
   for group in p:
    if group.name.startswith('02_'):group.visible=group.name=='02_'+state
  original=np.array(src.composite(force=True));trial=np.array(saved.composite(force=True))
  region=np.zeros((2048,2048),bool);region[400:1230,620:1250]=True;region&=original[:,:,3]==255
  diff=np.abs(trial.astype('int16')-original.astype('int16'));assert not diff[region].any()
  state_checks.append({'state':state,'central_opaque_face_max_difference':int(diff[region].max()),'region_xyxy':[620,400,1250,1230]})
 dump(OUT/'verification.json',{'input_psd_sha256':sha(SOURCE),'saved_psd_sha256':sha(path),'pixel_layers':46,'old_44_layers_pixels_offsets_retained':True,'old_44_layers_opacity_blend_and_clipping_retained':True,'old_R01_L01_hidden_only':True,'central_opaque_face_and_eyes_unchanged':True,'saved_psd_state_checks':state_checks,'records':records,'status':'two complete redrawn hair assets and a trial head assembly; other six locks remain visible-only cuts; roots/occlusion and physics still require review'})
 print(json.dumps({'pixel_layers':46,'records':records,'central_face_unchanged':True},indent=2))
if __name__=='__main__':main()
