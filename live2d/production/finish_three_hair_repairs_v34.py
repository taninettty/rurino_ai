"""Finish left fringe tip, right small-tail notch and contaminated thin hair.
Edits current left-view raster materials. Inferred repaint, no Cubism rig.
"""
import argparse,gc,json,re
from pathlib import Path
import numpy as np,cv2
from scipy.ndimage import distance_transform_edt,binary_fill_holes,gaussian_filter1d
from scipy.interpolate import PchipInterpolator
from PIL import Image,ImageDraw,ImageFont
from psd_tools import PSDImage
from psd_tools.api.layers import Group,PixelLayer
from outline_hair_layers_v34 import ROOT,W,H,DX,FONT,pixels,copy_pixel,paste_full,tiled,set_state,checker,sha
SOURCE=ROOT/'rebuild_v3_4/turn_redraw/bangs_contour_repair/Rurino_Bangs_Contour_Repaired_v034.psd'
OUT=ROOT/'rebuild_v3_4/turn_redraw/three_hair_finish'
PSD=OUT/'Rurino_Three_Hair_Repairs_v034.psd'

def full(l):return paste_full(l.topil().convert('RGBA'),l.offset)
def coords(b):
 y,x=np.indices((b[3]-b[1],b[2]-b[0]));return x+b[0],y+b[1]
def crop(im,b):return np.array(im.crop((DX+b[0],b[1],DX+b[2],b[3])))
def put(im,a,b):
 out=im.copy();out.paste(Image.fromarray(a),(DX+b[0],b[1]));return out

def mask(path,b):
 tok=re.findall(r'[MLCQZ]|-?\d+(?:\.\d+)?',path);p=np.zeros(2);pts=[];i=0
 while i<len(tok):
  op=tok[i];i+=1;n={'M':2,'L':2,'Q':4,'C':6,'Z':0}[op];v=np.array([float(z) for z in tok[i:i+n]]).reshape(-1,2);i+=n
  if op in ['M','L']:p=v[0];pts.append(p)
  elif op in ['Q','C']:
   for t in np.linspace(0,1,150)[1:]:pts.append((1-t)**2*p+2*(1-t)*t*v[0]+t*t*v[1] if op=='Q' else (1-t)**3*p+3*(1-t)**2*t*v[0]+3*(1-t)*t*t*v[1]+t**3*v[2])
   p=v[-1]
 size=(b[2]-b[0],b[3]-b[1]);im=Image.new('L',(size[0]*4,size[1]*4));ImageDraw.Draw(im).polygon([((x-b[0])*4,(y-b[1])*4) for x,y in pts],fill=255)
 return np.array(im.resize(size,Image.Resampling.LANCZOS))

def ink(alpha,width):
 h,w=alpha.shape;up=np.array(Image.fromarray(alpha).resize((w*4,h*4),Image.Resampling.LANCZOS));m=(up>127).astype('uint8')
 d=cv2.distanceTransform(np.pad(m,1),cv2.DIST_L2,5)[1:-1,1:-1]/4-.125
 cov=np.clip((width+.3-d)/.6,0,1)*m
 aa=np.array(Image.fromarray(np.rint(cov*235).astype('uint8')).resize((w,h),Image.Resampling.LANCZOS))
 out=np.zeros((h,w,4),np.uint8);out[:,:,3]=np.minimum(aa,alpha);return out

def clean_edge(old,alpha,weight,depth=14,minlum=145):
 d=cv2.distanceTransform((old[:,:,3]>127).astype('uint8'),cv2.DIST_L2,5)
 valid=(d>depth)&(old[:,:,:3].mean(axis=2)>minlum)
 nn=distance_transform_edt(~valid,return_distances=False,return_indices=True)
 colour=cv2.GaussianBlur(old[:,:,:3][nn[0],nn[1]],(0,0),2)
 nd=cv2.distanceTransform((alpha>127).astype('uint8'),cv2.DIST_L2,5)
 t=np.maximum(np.clip((depth+5-d)/6,0,1),np.clip((depth-nd)/5,0,1))*weight
 t=np.maximum(t,((old[:,:,3]==0)&(alpha>0)).astype(float))
 a=old.copy();a[:,:,:3]=np.rint(a[:,:,:3]*(1-t[:,:,None])+colour*t[:,:,None]).astype('uint8');a[:,:,3]=alpha;a[alpha==0]=0;return a

def blend_ink(old,new,t,alpha):
 out=old.copy();out[:,:,3]=np.minimum(np.rint(old[:,:,3]*(1-t)+new[:,:,3]*t).astype('uint8'),alpha);return out

def comparison(before,after,b,title,path,scale):
 font=ImageFont.truetype(FONT,22);w=round((b[2]-b[0])*scale);h=round((b[3]-b[1])*scale)
 out=Image.new('RGB',(2*w+60,h+100),'#e8edf3');d=ImageDraw.Draw(out)
 for i,(label,im) in enumerate([('修改前',before),('修改后',after)]):
  a=im.crop((DX+b[0],b[1],DX+b[2],b[3])).resize((w,h),Image.Resampling.LANCZOS);bg=checker(a.size);bg.paste(a,(0,0),a);out.paste(bg,(15+i*(w+30),55));d.text((15+i*(w+30),15),label+' · '+title,font=font,fill='#26394c')
 d.text((15,h+68),'静态材料修整；尚未绑定 Cubism 动作。',font=ImageFont.truetype(FONT,17),fill='#52647a');out.save(path,quality=97)

def prepare():
 for d in ['layers','qa','masks']:(OUT/d).mkdir(parents=True,exist_ok=True)
 src=PSDImage.open(SOURCE);old={l.name:l for l in pixels(src)};changed={}
 # Left fringe: retain unequal paired tips and replace only their lower edges.
 b=(530,560,720,810);x,y=coords(b);base=full(old['Crown']);a=crop(base,b)
 shape=mask('M 552 600 C 548 653 568 704 605 735 C 600 725 597 718 594 712 C 607 725 630 751 644 768 C 636 746 636 723 642 700 C 648 667 661 625 675 600 Z',b)
 t=np.clip((y-610)/40,0,1);t=t*t*(3-2*t);alpha=np.rint(a[:,:,3]*(1-t)+shape*t).astype('uint8')
 alpha[binary_fill_holes(alpha>127)&~(alpha>127)]=255
 fixed=clean_edge(a,alpha,t,depth=12,minlum=170);changed['Crown']=put(base,fixed,b)
 oldink=crop(full(old['Ink_Crown']),b);newink=blend_ink(oldink,ink(alpha,2.5),t,alpha);changed['Ink_Crown']=put(full(old['Ink_Crown']),newink,b)
 # Eye-front copy must use exactly the same repaired silhouette and ink.
 fg=crop(full(old['Left_Fringe_EyeOverlap_SOURCE']),b);fi=crop(full(old['Ink_Overlap_Left_Fringe_EyeOverlap_SOURCE']),b)
 fade=np.clip((y-680)/20,0,1)
 nf=fixed.copy();nf[:,:,3]=np.rint(alpha*fade).astype('uint8');nf[nf[:,:,3]==0]=0
 ni=newink.copy();ni[:,:,3]=np.rint(ni[:,:,3]*fade).astype('uint8')
 changed['Left_Fringe_EyeOverlap_SOURCE']=put(full(old['Left_Fringe_EyeOverlap_SOURCE']),nf,b)
 changed['Ink_Overlap_Left_Fringe_EyeOverlap_SOURCE']=put(full(old['Ink_Overlap_Left_Fringe_EyeOverlap_SOURCE']),ni,b)
 # Supply a narrow skin margin beneath changed hair; keep original face intact.
 skin=crop(full(old['FacePaint_AfterCheekRecovery_SOURCE']),b);good=(skin[:,:,3]>220)&(skin[:,:,0]>230)&(skin[:,:,1]>185)
 nn=distance_transform_edt(~good,return_distances=False,return_indices=True);col=cv2.GaussianBlur(skin[:,:,:3][nn[0],nn[1]],(0,0),3)
 reveal=((a[:,:,3]>0)|(fg[:,:,3]>0))&(alpha<255)&(t>0);support=cv2.dilate(reveal.astype('uint8'),np.ones((7,7),np.uint8))*255
 patch=np.dstack([col,support]);patch[support==0]=0
 back=full(old['Fringe_Edge_Skin_Underlap_LOCAL']);q=crop(back,b);q=np.array(Image.alpha_composite(Image.fromarray(q),Image.fromarray(patch)));changed['Fringe_Edge_Skin_Underlap_LOCAL']=put(back,q,b)
 Image.fromarray(support).save(OUT/'masks/left-tip-skin-margin.png')
 # Right small tail: smooth the 13px rectangular protrusion, keep the fork tip.
 b=(1420,720,1570,940);x,y=coords(b);base=full(old['Small_R']);a=crop(base,b)
 left=PchipInterpolator([720,760,800,850,880,905,940],[1456,1468,1481,1495,1500,1502,1510])(y[:,0])[:,None]
 limit=np.rint(np.clip(x-left+.5,0,1)*255).astype('uint8');target=np.minimum(a[:,:,3],limit)
 band=(x<left+np.clip((909-y)*1.5,0,8))&(y>780)&(y<909);target[band]=limit[band]
 target=cv2.GaussianBlur(target,(0,0),.65)
 t=np.clip((y-755)/25,0,1)*np.clip((925-y)/20,0,1);alpha=np.rint(a[:,:,3]*(1-t)+target*t).astype('uint8')
 # Affect only the outer rim at this notch, not the long inner source flow line.
 t*=np.clip((left+24-x)/10,0,1)
 fixed=clean_edge(a,alpha,t,depth=10,minlum=130);changed['Small_R']=put(base,fixed,b)
 oldink=crop(full(old['Ink_Small_R']),b);li=blend_ink(oldink,ink(alpha,2.6),t,alpha);changed['Ink_Small_R']=put(full(old['Ink_Small_R']),li,b)
 # Thin strand: repaint the contaminated stem continuously across its width.
 # Cross-section follows each row's real curved alpha, never a rectangular fill.
 b=(1350,730,1710,2140);x,y=coords(b);base=full(old['Thin_R']);a=crop(base,b)
 smooth=cv2.GaussianBlur(a[:,:,3],(0,0),.65);alpha=smooth
 valid=alpha>127;le=np.array([np.flatnonzero(r)[0] if r.any() else 0 for r in valid],float);ri=np.array([np.flatnonzero(r)[-1] if r.any() else 1 for r in valid],float)
 le=gaussian_filter1d(le,7);ri=gaussian_filter1d(ri,7)
 contour=np.rint(np.clip(np.minimum(x-b[0]-le[:,None]+.5,ri[:,None]-(x-b[0])+.5),0,1)*255).astype('uint8')
 w=np.clip((y-790)/70,0,1)*np.clip((1940-y)/80,0,1);alpha=np.rint(alpha*(1-w)+contour*w).astype('uint8')
 u=np.clip((x-b[0]-le[:,None])/np.maximum(ri-le,1)[:,None],0,1)
 knots=[900,1200,1450,1700,1850]
 palettes=np.array([
  [[209,167,179],[226,187,192],[233,198,197],[224,185,190]],
  [[203,160,174],[231,190,189],[252,232,193],[246,223,190]],
  [[215,177,180],[240,211,184],[255,239,201],[249,228,187]],
  [[233,211,185],[249,235,196],[250,241,206],[232,224,192]],
  [[164,179,220],[190,216,230],[211,238,229],[175,198,221]],
 ],float)
 rowpal=np.stack([[np.interp(y[:,0],knots,palettes[:,j,k]) for k in range(3)] for j in range(4)],axis=1).transpose(2,1,0)
 colour=np.zeros_like(a[:,:,:3],float)
 for row in range(len(le)):
  for k in range(3):colour[row,:,k]=np.interp(u[row],np.linspace(0,1,4),rowpal[row,:,k])
 # Transition before the first broken strokes, then into the retained blue curl.
 t=np.clip((y-900)/70,0,1)*np.clip((1870-y)/80,0,1);t=t*t*(3-2*t)
 fixed=a.copy();fixed[:,:,:3]=np.rint(a[:,:,:3]*(1-t[:,:,None])+colour*t[:,:,None]).clip(0,255).astype('uint8');fixed[:,:,3]=alpha
 # Clean surviving dark contour remnants on the lower curl; preserve its shading.
 edgefixed=clean_edge(fixed,alpha,np.clip((y-1790)/90,0,1),depth=5,minlum=120)
 fixed=edgefixed;fixed[alpha==0]=0
 # A continuous, tapered mauve interior line follows the stem's own curvature.
 flow=Image.new('RGBA',(fixed.shape[1]*4,fixed.shape[0]*4));d=ImageDraw.Draw(flow);prev=None
 for yy in range(920,1770):
  row=yy-b[1];uu=.31+.10*np.sin((yy-920)/850*np.pi);xx=b[0]+le[row]+uu*(ri[row]-le[row]);fade=min((yy-920)/90,(1770-yy)/160,1);fade=max(fade,0)
  if prev:d.line((prev[0],prev[1],(xx-b[0])*4,(yy-b[1])*4),fill=(128,94,120,round(150*fade)),width=max(1,round(2.2*fade*4)))
  prev=((xx-b[0])*4,(yy-b[1])*4)
 line=np.array(flow.resize((fixed.shape[1],fixed.shape[0]),Image.Resampling.LANCZOS));line[:,:,3]=np.minimum(line[:,:,3],alpha)
 merged=np.array(Image.alpha_composite(Image.fromarray(fixed),Image.fromarray(line)));fixed[:,:,:3]=merged[:,:,:3]
 changed['Thin_R']=put(base,fixed,b);li=ink(alpha,2.0);li[:,:,3]=np.rint(li[:,:,3]*np.clip((y-970)/110,0,1)).astype('uint8');changed['Ink_Thin_R']=put(full(old['Ink_Thin_R']),li,b)
 for n,im in changed.items():im.save(OUT/'layers'/(n+'.png'))
 for n,b,title,scale in [('Crown',(540,600,700,790),'左侧刘海发尖',2.5),('Small_R',(1440,770,1560,930),'右小马尾内缘',2.5),('Thin_R',(1360,900,1600,1870),'右侧细长发',1.0)]:
  bef=Image.alpha_composite(full(old[n]),full(old['Ink_'+n]));aft=Image.alpha_composite(changed[n],changed['Ink_'+n]);aft.save(OUT/'qa'/(n+'-repaired.png'))
  comparison(bef,aft,b,title,OUT/'qa'/('three-repair-'+n+'.jpg'),scale)
 report={'source_psd':str(SOURCE.relative_to(ROOT)),'source_sha256':sha(SOURCE),'changed_layers':list(changed),'scope':'left fringe tip, right small-tail notch, contaminated thin strand; current left-view raster only','inferred_paint':['local fringe contour colours and exposed skin','thin hair stem pink/gold/blue colour and continuous flow stroke'],'new_cubism_rig':False}
 (OUT/'edit-record.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,indent=2),flush=True)

def build():
 source=PSDImage.open(SOURCE);old={l.name:l for l in pixels(source)};files={p.stem:p for p in (OUT/'layers').glob('*.png')};psd=PSDImage.new('RGBA',(W,H),color=0)
 def clone(items,parent):
  for l in items:
   if l.is_group():
    g=Group.new(l.name,parent=parent);g.visible=l.visible;g.opacity=l.opacity
    if l.blend_mode is not None:g.blend_mode=l.blend_mode
    clone(l,g)
   elif l.name in files:
    im=Image.open(files[l.name]).convert('RGBA');b=im.getbbox();n=PixelLayer.frompil(im.crop(b),psd_file=psd,layer_name=l.name,left=b[0],top=b[1]);parent.append(n);n.visible=l.visible;n.opacity=l.opacity;n.clipping_layer=l.clipping_layer
    if l.blend_mode is not None:n.blend_mode=l.blend_mode
   else:copy_pixel(l,parent,psd)
 clone(source,psd);set_state(psd,'Open');default=tiled(psd);print('Rendered Open',flush=True)
 psd._update_record();psd._record.image_data.set_data([c.tobytes() for c in default.split()],psd._record.header)
 with PSD.open('wb') as f:psd._record.write(f)
 del psd;gc.collect();saved=PSDImage.open(PSD);new={l.name:l for l in pixels(saved)};preserved=[]
 for n,l in old.items():
  q=new[n];assert (l.visible,l.opacity,l.blend_mode,l.clipping_layer)==(q.visible,q.opacity,q.blend_mode,q.clipping_layer),n
  if n in files:
   im=Image.open(files[n]);b=im.getbbox();assert tuple(q.bbox)==b and np.array_equal(np.array(q.topil().convert('RGBA')),np.array(im.crop(b))),n
  else:
   assert l.offset==q.offset and np.array_equal(np.array(l.topil()),np.array(q.topil())),n;preserved.append(n)
 assert np.array_equal(np.array(default),np.array(tiled(saved)))
 audit=[]
 for n in ['Crown','Small_R','Thin_R']:
  a=np.array(Image.open(files[n]));m=a[:,:,3]>127;c,_,stats,_=cv2.connectedComponentsWithStats(m.astype('uint8'),8);count=int((stats[1:,cv2.CC_STAT_AREA]>8).sum());holes=int((binary_fill_holes(m)&~m).sum());assert count==1 and holes==0,(n,count,holes)
  audit.append({'part':n,'major_connected_components':count,'enclosed_hole_pixels':holes})
 states=[]
 for state in ['Open','Half','Closed']:
  set_state(saved,state);im=default if state=='Open' else tiled(saved);p=OUT/'qa'/('three-repairs-assembled-'+state+'.png');im.save(p);states.append({'state':state,'sha256':sha(p)});print('Verified',state,flush=True)
 previous=Image.open(SOURCE.parent/'qa/bangs-assembled-Open.png').convert('RGBA');ba=np.array(previous);aa=np.array(default)
 roi=(slice(610,800),slice(DX+530,DX+720));gaps=int(((ba[roi][:,:,3]>250)&(aa[roi][:,:,3]<240)).sum());assert gaps==0,gaps
 comparison(previous,default,(400,80,1510,1200),'整头合成',OUT/'qa/three-repairs-head.jpg',.6)
 # Full bust catches thin-hair contamination that a head-only preview hides.
 comparison(previous,default,(250,0,1790,2180),'含细长发的装配',OUT/'qa/three-repairs-bust.jpg',.45)
 font=ImageFont.truetype(FONT,22);sheet=Image.new('RGB',(1440,650),'#e8edf3');d=ImageDraw.Draw(sheet)
 for i,state in enumerate(['Open','Half','Closed']):
  im=Image.open(OUT/'qa'/('three-repairs-assembled-'+state+'.png')).crop((DX+400,80,DX+1510,1200));im.thumbnail((465,560));bg=checker(im.size);bg.paste(im,(0,0),im);sheet.paste(bg,(i*480+8,50));d.text((i*480+10,12),{'Open':'睁眼','Half':'半闭眼','Closed':'闭眼'}[state],font=font,fill='#26394c')
 sheet.save(OUT/'qa/three-repairs-eye-states.jpg',quality=97)
 report=json.loads((OUT/'edit-record.json').read_text());report.update({'psd':PSD.name,'sha256':sha(PSD),'canvas':[W,H],'pixel_layers':len(new),'unchanged_layers':preserved,'unchanged_rgba_offsets_properties_exact':True,'edited_layers_roundtrip_exact':True,'saved_default_matches_preview':True,'new_left_fringe_transparent_gaps':gaps,'hair_alpha_audit':audit,'states':states})
 (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'psd':str(PSD),'layers':len(new),'preserved':len(preserved),'changed':len(files),'sha256':sha(PSD)},indent=2),flush=True)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--build',action='store_true');args=p.parse_args()
 if args.build:build()
 else:prepare()
