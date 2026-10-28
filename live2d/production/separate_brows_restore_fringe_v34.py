"""Local eyebrow extraction and narrow under-brow repair, retaining unsplit fringe.
This is deterministic raster editing, not a generated redraw or completed rig.
"""
import json
from pathlib import Path
import cv2,numpy as np
from scipy.interpolate import PchipInterpolator
from PIL import Image,ImageDraw,ImageFont
from psd_tools import PSDImage
from psd_tools.api.layers import Group
from split_left_head_parts_v34 import TURN,pixels,clone,add,sha
from build_hair_flow_redraw_v34 import full
SOURCE=TURN/'fringe_overlap_separation/Rurino_Crown_Fringe_Overlap_Separated_v034.psd'
OUT=TURN/'brows_clean_fringe_repair'
FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
# Native 2048 pixel coordinates, traced against enlarged original contours.
CURVES={
'L':([562,580,600,620,640,660,680,700,720,740,752],
     [692,675,658,646,636,630,629,632,640,653,666],
     [692,678,665,656,650,646,644,645,648,657,666]),
'R':([910,930,950,970,990,1010,1030,1050,1070,1090,1110,1130,1150,1170,1190,1205,1216],
     [665,649,637,630,626,624,624,626,629,633,639,645,652,661,671,682,688],
     [665,653,646,642,640,639,639,640,642,646,651,657,663,669,676,683,688])}

def brow_shape(side,head):
 x,t,b=CURVES[side];xs=np.arange(x[0],x[-1]+1);tf=PchipInterpolator(x,t);bf=PchipInterpolator(x,b)
 lum=cv2.GaussianBlur(cv2.cvtColor(head[:,:,:3],cv2.COLOR_RGB2GRAY),(3,3),.55)
 crosses={'L':[570,600,661],'R':[962,988,1045,1148,1157,1200]}[side]
 safe=(bf(xs)-tf(xs)>5)
 for cross in crosses:safe&=abs(xs-cross)>6
 ys=[]
 for f in [tf,bf]:
  centers=[]
  for xx in xs[safe]:
   yy=int(round(float(f(xx))));span=np.arange(yy-4,yy+5);centers.append(float(span[np.argmin(lum[span,xx])]))
  fit=np.polynomial.Polynomial.fit(np.r_[xs[safe],xs[0],xs[-1]],np.r_[centers,f(xs[0]),f(xs[-1])],4,w=np.r_[np.ones(len(centers)),12,12])
  vals=fit(xs);vals-=np.linspace(vals[0]-f(xs[0]),vals[-1]-f(xs[-1]),len(xs));ys.append(vals)
 top,bottom=np.minimum(ys[0],ys[1]),np.maximum(ys[0],ys[1])
 # Build a clean antialiased silhouette around the two traced stroke centers.
 yy,xx=np.indices((2048,2048));upper=np.interp(xx,xs,top);lower=np.interp(xx,xs,bottom)
 taper=np.minimum(1,np.minimum((xx-xs[0])/7,(xs[-1]-xx)/7));margin=1.15*np.clip(taper,0,1)
 aa=np.clip(np.minimum(yy-upper+margin,lower+margin-yy)+.5,0,1)
 aa[:, :xs[0]]=0;aa[:,xs[-1]+1:]=0
 return np.rint(aa*255).astype('uint8'),xs,top,bottom,safe

def clean_brow(head,shape):
 m,xs,top,bottom,safe=shape
 # Resample original brow colors along its arc; rebuild contaminated edge
 # intersections using neighbouring brow samples, never the hair behind it.
 us=np.linspace(-.3,1.3,97);mx=np.broadcast_to(xs[None,:],(len(us),len(xs))).astype('float32')
 my=(top[None,:]+us[:,None]*(bottom-top)[None,:]).astype('float32')
 profile=cv2.remap(head[:,:,:3].astype('float32'),mx,my,cv2.INTER_LINEAR)
 clean=profile.copy()
 for i,u in enumerate(us):
  for c in range(3):clean[i,:,c]=np.interp(xs,xs[safe],profile[i,safe,c])
 # Keep original interior where safe; line profiles at the outer edge are
 # smoothly continued to avoid short vertical hair stubs riding on the brows.
 out=np.zeros_like(head);yy,xx=np.where(m>0);idx=xx-xs[0]
 v=(yy-top[idx])/np.maximum(bottom[idx]-top[idx],.4)
 row=np.clip((v-us[0])/(us[-1]-us[0])*(len(us)-1),0,len(us)-1).astype('float32')
 rgb=cv2.remap(clean,idx[None,:].astype('float32'),row[None,:],cv2.INTER_LINEAR)[0]
 out[yy,xx,:3]=np.clip(np.rint(rgb),0,255).astype('uint8');out[:,:,3]=m
 return out

def checker(size):
 yy,xx=np.indices((size[1],size[0]));a=np.where(((xx//16+yy//16)%2)[:,:,None],np.array([201,212,224]),np.array([234,239,245]));return Image.fromarray(a.astype('uint8'))


# Observed longitudinal line positions, at native y coordinates. These guide
# narrow interpolation only; they do not warp any existing visible pixel.
FLOW_Y=np.array([590,610,630,650,670,690,710,730])
FLOW={
 'L':np.array([[530]*8,[548,550,554,561,568,577,587,598],[587,589,592,597,602,609,616,624],[679,671,663,655,648,641,635,630],[790]*8]),
 'R':np.array([[880]*8,[958,960,962,964,965,965,963,961],[991,990,988,985,981,977,973,967],[1025,1038,1051,1062,1074,1085,1096,1105],[1157,1155,1151,1145,1135,1125,1113,1105.5],[1161,1160,1159,1158,1157,1156,1153,1148],[1209,1211,1209,1206,1200,1193,1185,1175],[1250]*8])}

def flow_coordinates(remove):
 yy,xx=np.where(remove>0);upx=xx.astype('float32');upy=yy.astype('float32');dnx=upx.copy();dny=upy.copy()
 for side in ['L','R']:
  pick=xx<800 if side=='L' else xx>800;x=xx[pick];y=yy[pick]
  fs=[PchipInterpolator(FLOW_Y,c,extrapolate=True) for c in FLOW[side]]
  lines=np.stack([f(y) for f in fs]);idx=np.clip((x[None,:]>=lines).sum(axis=0)-1,0,len(fs)-2)
  lo=lines[idx,np.arange(len(x))];hi=lines[idx+1,np.arange(len(x))];u=np.clip((x-lo)/(hi-lo),0,1)
  def mapx(ys):
   ls=np.stack([f(ys) for f in fs]);return ls[idx,np.arange(len(x))]*(1-u)+ls[idx+1,np.arange(len(x))]*u
  for sign,xout,yout in [(-1,upx,upy),(1,dnx,dny)]:
   ys=y.copy();xs=x.astype(float);done=np.zeros(len(x),bool)
   for step in range(1,90):
    qy=y+sign*step;qx=mapx(qy);ix=np.clip(np.rint(qx).astype(int),0,2047)
    hit=(remove[qy,ix]==0)&~done;ys[hit]=qy[hit];xs[hit]=qx[hit];done|=hit
    if done.all():break
   assert done.all()
   xout[pick]=xs;yout[pick]=ys
 return yy,xx,upx,upy,dnx,dny

def flow_fill(a,remove,coords=None):
 if coords is None:coords=flow_coordinates(remove)
 yy,xx,upx,upy,dnx,dny=coords
 f=a.astype('float32')/255;f[:,:,:3]*=f[:,:,3:4]
 def sample(mx,my):return cv2.remap(f,mx[None,:],my[None,:],cv2.INTER_LINEAR)[0]
 t=((yy-upy)/(dny-upy))[:,None];v=sample(upx,upy)*(1-t)+sample(dnx,dny)*t
 v[:,:3]/=np.maximum(v[:,3:4],1e-6);v=np.clip(np.rint(v*255),0,255).astype('uint8');v[v[:,3]==0]=0
 out=a.copy();out[yy,xx]=v;return out

def prepare():
 for n in ['layers','masks','qa']:(OUT/n).mkdir(parents=True,exist_ok=True)
 head=np.array(Image.open(TURN/'fringe_overlap_separation/qa/saved-psd-open.png').convert('RGBA'))
 shapes={s:brow_shape(s,head) for s in CURVES};masks={s:v[0] for s,v in shapes.items()};region=np.maximum.reduce(list(masks.values()))>0
 remove=cv2.dilate(region.astype('uint8'),np.ones((9,9),np.uint8))
 repaired=flow_fill(head,remove)
 brows={}
 for s,m in masks.items():
  a=clean_brow(head,shapes[s]);brows[s]=a;Image.fromarray(a).save(OUT/'layers'/f'Eyebrow_{s}_Full.png')
  Image.fromarray(m).save(OUT/'masks'/f'brow-{s}.png')
 Image.fromarray(remove*255).save(OUT/'masks/under-brow-edit.png')
 Image.fromarray(repaired).save(OUT/'qa/no-brows-local-repair.png')
 sheet=Image.new('RGB',(1440,720),'#e8edf3');d=ImageDraw.Draw(sheet);font=ImageFont.truetype(FONT,20)
 for row,(s,box) in enumerate([('L',(540,600,775,725)),('R',(895,595,1240,730))]):
  for col,(label,arr) in enumerate([('原图',head),('独立眉毛',brows[s]),('补接后 · 隐藏眉毛',repaired)]):
   x=col*480;y=row*360;tile=checker((460,285));im=Image.fromarray(arr).crop(box);im.thumbnail((450,270));tile.paste(im,((460-im.width)//2,(285-im.height)//2),im);sheet.paste(tile,(x+10,y+50));d.text((x+12,y+13),s+' · '+label,font=font,fill='#26394c')
 sheet.save(OUT/'qa/brow-repair-review.jpg',quality=97)
 return head,repaired,masks,brows,remove



def main():
 head,repaired,masks,brows,remove=prepare();region=remove>0;coords=flow_coordinates(remove)
 source=PSDImage.open(SOURCE);lookup={l.name:l for l in pixels(source)}
 replaced={'CrownFringe_L_BrowPatchRemoved_SHARED','CrownFringe_R_BrowPatchRemoved_SHARED','BrowOverlap_L_FromHair_PATCH_ONLY','BrowOverlap_R_FromHair_PATCH_ONLY'}
 candidates={}
 for group in source:
  if not group.visible or group.name.startswith('02_'):continue
  for l in pixels(group):
   if l.name in replaced:continue
   if l.visible or l.name in ['Bang_ImageLeft_Visible','Bang_ImageRight_Visible']:
    arr=full(l)
    if (arr[:,:,3][region]>0).any():candidates[l.name]=arr
 # Interpolate ownership along traced flow in the narrow repaired band only.
 # A single owner per opaque repaired pixel avoids overlapping soft alpha gaps.
 proposals={n:flow_fill(a,remove,coords) for n,a in candidates.items()}
 yy,xx=np.where(region);scores=np.stack([a[yy,xx,3] for a in proposals.values()]);owners=np.argmax(scores,axis=0)
 repaired_parts={};records=[]
 for i,(n,a) in enumerate(candidates.items()):
  arr=a.copy();arr[yy,xx]=0;pick=owners==i;arr[yy[pick],xx[pick]]=repaired[yy[pick],xx[pick]];arr[arr[:,:,3]==0]=0
  assert np.array_equal(arr[~region][a[~region][:,3]>0],a[~region][a[~region][:,3]>0])
  newname={'Bang_ImageLeft_Visible':'CrownFringe_L_BrowRemoved_REPAIRED','Bang_ImageRight_Visible':'CrownFringe_R_BrowRemoved_REPAIRED'}.get(n,n+'_BrowRemoved_LOCAL')
  repaired_parts[n]=(newname,arr);Image.fromarray(arr).save(OUT/'layers'/(newname+'.png'))
  records.append({'source_layer':n,'new_layer':newname,'edited_alpha_pixels':int((arr[region,3]>0).sum()),'outside_edit_mask_visible_pixels_unchanged':True})
 psd=PSDImage.new('RGBA',(2048,2048),color=0);clone(source,psd,psd,[]);dest={l.name:l for l in pixels(psd)}
 for n,(newname,arr) in repaired_parts.items():
  old=dest[n];parent=old.parent;index=list(parent).index(old);new=add(psd,parent,Image.fromarray(arr),newname);parent.remove(new);parent.insert(index,new);new.visible=True;old.visible=False
 for n in replaced:dest[n].visible=False
 bg=Group.new('04_Independent_Brows_LOCAL_CLEANUP',parent=psd)
 for side,arr in brows.items():add(psd,bg,Image.fromarray(arr),'Eyebrow_'+side+'_Full_LOCAL_CLEANUP')
 path=OUT/'Rurino_Brows_Separated_Fringe_Repaired_v034.psd';psd.save(path)
 saved=PSDImage.open(path);after={l.name:l for l in pixels(saved)}
 for n,old in lookup.items():
  new=after[n];assert old.offset==new.offset and np.array_equal(np.array(old.topil()),np.array(new.topil())),n
  assert (old.opacity,old.blend_mode,old.clipping_layer)==(new.opacity,new.blend_mode,new.clipping_layer),n
  assert new.visible==(False if n in replaced or n in repaired_parts else old.visible),n
 for newname,arr in repaired_parts.values():assert np.array_equal(full(after[newname]),arr),newname
 for side,arr in brows.items():assert np.array_equal(full(after['Eyebrow_'+side+'_Full_LOCAL_CLEANUP']),arr),side
 states=[]
 for state in ['Open','Half','Closed']:
  for doc in [source,saved]:
   for g in doc:
    if g.name.startswith('02_'):g.visible=g.name=='02_'+state
  before=np.array(source.composite(force=True));actual=np.array(saved.composite(force=True));assert np.array_equal(before[~region],actual[~region]),state
  states.append({'state':state,'outside_brow_edit_mask_rgba_exact':True,'changed_pixels_inside_mask':int(np.any(actual[region]!=before[region],axis=1).sum())})
  if state=='Open':Image.fromarray(actual).save(OUT/'qa/saved-psd-open.png')
 for g in saved:
  if g.name.startswith('02_'):g.visible=g.name=='02_Open'
  if g.name=='04_Independent_Brows_LOCAL_CLEANUP':g.visible=False
 no_brows=np.array(saved.composite(force=True));Image.fromarray(no_brows).save(OUT/'qa/saved-psd-brows-hidden.png')
 # Actual saved-layer display and hide checks, not rectangular composite crops.
 sheet=Image.new('RGB',(1400,930),'#e8edf3');d=ImageDraw.Draw(sheet);font=ImageFont.truetype(FONT,22)
 for i,side in enumerate(['L','R']):
  arr=full(after['CrownFringe_'+side+'_BrowRemoved_REPAIRED']);box=Image.fromarray(arr[:,:,3]).getbbox();im=Image.fromarray(arr).crop(box);im.thumbnail((540,730));tile=checker((650,780));tile.paste(im,((650-im.width)//2,20),im);sheet.paste(tile,(i*700+25,70));d.text((i*700+25,20),side+' · 连续刘海层 / 眉下缺口已局部补接',font=font,fill='#26394c')
 d.text((25,875),'实际 PSD 独立图层。共用上部保持连续；隐藏发根与其他边缘尚未全部补全。',font=font,fill='#52647a');sheet.save(OUT/'qa/fringe-repaired-full-alpha.jpg',quality=97)
 # Replace prototype no-brow panel with the actual saved PSD rendering.
 repair_image=Image.open(OUT/'qa/brow-repair-review.jpg')
 for row,(side,box) in enumerate([('L',(540,600,775,725)),('R',(895,595,1240,730))]):
  tile=checker((460,285));im=Image.fromarray(no_brows).crop(box);im.thumbnail((450,270));tile.paste(im,((460-im.width)//2,(285-im.height)//2),im);repair_image.paste(tile,(970,row*360+50))
 repair_image.save(OUT/'qa/brow-repair-review.jpg',quality=97)
 report={'input_psd_sha256':sha(SOURCE),'saved_psd_sha256':sha(path),'pixel_layers':len(after),'original_66_layer_pixels_and_attributes_preserved':True,'rejected_CD_split_used':False,'fringe_further_split':False,'independent_full_brows':2,'brow_method':'original arc/colour sampled; crossing hair remnants and matte locally cleaned, not pixel-exact source extraction','repair_method':'narrow directional interpolation along traced hair lines; per-pixel ownership rebuilt only in edit mask','edit_mask_pixels':int(region.sum()),'modified_sources':records,'states':states,'new_layers_match_pngs':True,'scope':'left-view head only; under-brow hair and skin repaired; remaining hair roots and hidden areas pending','generative_image_tasks_started':0,'new_mesh_or_physics':False}
 (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
