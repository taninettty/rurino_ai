"""Assemble repaired hair materials in the current left-view artwork.
Local concealed surfaces and off-canvas tips are inferred, not new angle keyforms.
"""
import argparse,json,gc
from pathlib import Path
import cv2,numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import gaussian_filter1d,distance_transform_edt,binary_fill_holes,label
from PIL import Image,ImageDraw,ImageFont
from psd_tools import PSDImage
from psd_tools.api.layers import Group
from split_left_head_parts_v34 import TURN,pixels,clone,add,sha
from build_hair_flow_redraw_v34 import full
from complete_hair_backplates_v34 import combine,profile
from complete_fringe_materials_v34 import checker,FONT
from split_head_v34 import mask as oldmask
SOURCE=TURN/'left_cheek_upper_surface/Rurino_Left_Cheek_Upper_Surface_v034.psd'
OUT=TURN/'whole_hair_static_completion'
W,H,DX=3456,2816,704
ROOTS={
 'Small_L':([210,300,450,600,750,850,930],[525,480,400,345,345,375,417],[550,610,550,490,450,440,435],(510,530,395,450)),
 'Small_R':([191,300,450,600,750,850,890],[1480,1420,1410,1430,1460,1495,1505],[1495,1600,1590,1570,1540,1520,1510],(510,530,1500,1580)),
 'Large_L':([330,500,750,1000,1200,1400,1600,1800,2048],[550,485,440,425,350,245,95,-70,-200],[570,630,710,820,900,820,600,390,240],(1290,1310,355,740)),
 'Large_R':([330,500,750,1000,1200,1400,1600,1800,2048],[1450,1380,1310,1200,1130,1220,1400,1600,1780],[1470,1540,1600,1660,1720,1830,1970,2120,2250],(1290,1310,1445,1735))}
def extended(a):
 out=np.zeros((H,W,4),np.uint8);out[:2048,DX:DX+2048]=a;return out
def native(a):return a[:2048,DX:DX+2048]
def band(y,l,r,h=2048,w=2048,dx=0):
 rows=np.arange(h);left=PchipInterpolator(y,l,extrapolate=False)(rows);right=PchipInterpolator(y,r,extrapolate=False)(rows);x=np.arange(w)-dx
 cov=np.nan_to_num(np.clip(np.minimum(x[None,:]-left[:,None]+.5,right[:,None]-x[None,:]+.5),0,1)).astype('float32')
 u=np.nan_to_num(np.clip((x[None,:]-left[:,None])/np.maximum(right[:,None]-left[:,None],1),0,1)).astype('float32');return cov,u

def repair_root(a,key):
 ys,l,r,box=ROOTS[key];cov,u=band(ys,l,r);pal=profile(a,box);colour=np.stack([np.interp(u,np.linspace(0,1,len(pal)),pal[:,k]) for k in range(3)],axis=2).astype('float32')
 if key.startswith('Small'):
  # Blue remains the source colour at the lower root; a gradual transition
  # prevents gold paint bleeding into existing blue inner ends.
  blue=np.array([173,205,231],np.float32);t=np.clip((np.arange(2048)-620)/230,0,1)[:,None,None];colour=colour*(1-t)+blue*t
 backing=np.zeros_like(a);backing[:,:,:3]=np.rint(colour).clip(0,255).astype('uint8');backing[:,:,3]=np.rint(cov*253).astype('uint8');backing[backing[:,:,3]==0]=0
 out=combine(backing,a)
 # Replace old occlusion-cut outlines only well inside the new hidden surface.
 oldin=cv2.distanceTransform((a[:,:,3]>220).astype('uint8'),cv2.DIST_L2,5);newin=cv2.distanceTransform((out[:,:,3]>220).astype('uint8'),cv2.DIST_L2,5)
 yy=np.arange(2048)[:,None];edge=(oldin>0)&(oldin<28)&(newin>24)&(cov>.99)
 edge&=((yy>970)&(yy<1510)) if key.startswith('Large') else ((yy>230)&(yy<720))
 w=np.clip((28-oldin)/20,0,1)*edge
 out[:,:,:3]=np.rint(out[:,:,:3]*(1-w[:,:,None])+colour*w[:,:,None]).clip(0,255).astype('uint8')
 out[out[:,:,3]==0]=0
 return out,{'added_root_pixels':int(((out[:,:,3]>0)&(a[:,:,3]==0)).sum()),'occlusion_seam_repaint_pixels':int(edge.sum())}

def small_cleanup(a,key):
 # Source cut boundaries at the inner rim must not survive as little teeth.
 yy,xx=np.indices((2048,2048));out=a.copy()
 if key=='Small_L':
  ys=[210,300,450,600,700,800,900,950,980];edge=[550,610,550,490,460,450,442,435,435]
  lim=PchipInterpolator(ys,edge,extrapolate=False)(np.arange(2048))[:,None]
  trim=(xx>lim)&(yy<950)
 else:
  ys=[191,300,450,600,700,800,890];edge=[1480,1420,1410,1430,1450,1480,1505]
  lim=PchipInterpolator(ys,edge,extrapolate=False)(np.arange(2048))[:,None]
  trim=(xx<lim)&(yy<850)
 out[trim]=0
 return out

def path_mask(path):
 import re
 tokens=re.findall(r'[MLCQZ]|-?\d+(?:\.\d+)?',path);i=0;p=np.zeros(2);points=[]
 while i<len(tokens):
  op=tokens[i];i+=1;n={'M':2,'L':2,'Q':4,'C':6,'Z':0}[op];vals=np.array([float(v) for v in tokens[i:i+n]]).reshape(-1,2);i+=n
  if op in ('M','L'):p=vals[0];points.append(p)
  elif op in ('Q','C'):
   for t in np.linspace(0,1,100)[1:]:points.append((1-t)**2*p+2*(1-t)*t*vals[0]+t*t*vals[1] if op=='Q' else (1-t)**3*p+3*(1-t)**2*t*vals[0]+3*(1-t)*t*t*vals[1]+t**3*vals[2])
   p=vals[-1]
 im=Image.new('L',(W*2,H*2));ImageDraw.Draw(im).polygon([(round((x+DX)*2),round(y*2)) for x,y in points],fill=255)
 return np.array(im.resize((W,H),Image.Resampling.LANCZOS)).astype('float32')/255

# Different independently drawn curls; based on the downward/outward sweep in
# the local official full-body reference, not mirrored copies of one tail.
TIP_PATH={
'L':'M -70 1800 C -190 1950 -245 2110 -220 2250 C -210 2350 -170 2390 -115 2420 C -160 2425 -205 2395 -220 2370 C -215 2465 -115 2500 -35 2460 C 15 2500 65 2540 30 2580 C 105 2560 120 2500 80 2445 C 155 2460 215 2500 190 2550 C 265 2505 255 2430 200 2390 C 115 2320 110 2235 155 2140 C 205 2030 300 1900 390 1800 Z',
'R':'M 1600 1800 C 1710 1950 1810 2075 1855 2180 C 1900 2290 1875 2360 1830 2405 C 1770 2465 1795 2525 1865 2555 C 1825 2500 1870 2470 1930 2440 C 1900 2510 1940 2565 2005 2570 C 1970 2525 1995 2485 2035 2450 C 2120 2490 2195 2440 2210 2375 C 2180 2405 2140 2420 2100 2405 C 2180 2350 2225 2260 2215 2160 C 2200 2020 2160 1910 2120 1800 Z'}

def finish_large(a,key):
 side=key[-1];base=extended(a);ys,l,r,_=ROOTS[key]
 # Extend root bands beyond the old horizontal canvas bounds without changing
 # the old image coordinate system. Tips are drawn as curved closed silhouettes.
 cov,u=band(ys,l,r,H,W,DX);cov[1800:]=0;tip=path_mask(TIP_PATH[side]);coverage=np.maximum(cov,tip)
 # Supply a continuous transverse colour profile across cropped source edges.
 if side=='L':cols=np.array([[142,145,200],[181,205,229],[211,239,226],[205,231,227],[160,170,216]],float)
 else:cols=np.array([[167,174,220],[207,231,229],[216,240,224],[174,201,226],[142,147,200]],float)
 x=np.arange(W)-DX;rows=np.arange(H)
 # Tip colour coordinates follow the curl centre rather than a rectangle.
 if side=='L':cy=[1750,2000,2200,2350,2500,2600];cl=[-50,-200,-230,-190,-80,30];cr=[420,250,145,150,240,80]
 else:cy=[1750,2000,2200,2350,2500,2600];cl=[1540,1760,1860,1860,1800,1900];cr=[2070,2200,2220,2170,2100,2000]
 _,ut=band(cy,cl,cr,H,W,DX);mix=np.clip((rows-1750)/200,0,1)[:,None];u=u*(1-mix)+ut*mix
 colour=np.stack([np.interp(u,np.linspace(0,1,len(cols)),cols[:,k]) for k in range(3)],axis=2).astype('float32')
 # At the cropped seam derive per-row colours from the original material;
 # fade into the lower blue palette over 300px.
 for y in range(1600,2048):
  source=a[y];valid=np.where(source[:,3]>220)[0]
  if len(valid)<20:continue
  vals=gaussian_filter1d(source[valid,:3].astype(float),8,axis=0);pal=np.stack([np.interp(np.linspace(0,len(valid)-1,128),np.arange(len(valid)),vals[:,k]) for k in range(3)],axis=1)
  row=np.stack([np.interp(u[y],np.linspace(0,1,128),pal[:,k]) for k in range(3)],axis=1)
  t=np.clip((y-1750)/350,0,1);colour[y]=row*(1-t)+colour[y]*t
 painted=np.zeros((H,W,4),np.uint8);painted[:,:,:3]=np.rint(colour).clip(0,255).astype('uint8');painted[:,:,3]=np.rint(coverage*253).astype('uint8');painted[coverage==0]=0
 # Blend the lower original to the inferred extension. Above 1750 source stays.
 t=np.clip((rows-1750)/298,0,1)[:,None,None];t=t*t*(3-2*t)
 present=base[:,:,3]>0;out=painted.copy();inside=np.s_[:2048,DX:DX+2048]
 merged=combine(painted,base);blend=np.rint(merged*(1-t)+painted*t).astype('uint8');out[present]=blend[present]
 # Original root/shoulder replacement already lives in a. Keep it exactly.
 out[:1750,DX:DX+2048]=a[:1750]
 out[(coverage==0)&((~present)|(np.arange(H)[:,None]>=1800))]=0
 # Soft outline only on newly inferred external lower contour, never source cuts.
 distance=cv2.distanceTransform((coverage>.5).astype('uint8'),cv2.DIST_L2,5);outline=(distance>0)&(distance<2)&(np.arange(H)[:,None]>1930)
 out[outline,:3]=np.rint(out[outline,:3]*.55+np.array([92,91,139])*.45).astype('uint8')
 # Tapered lavender shadow ribbons follow the same curls as the silhouette.
 shadow_paths={
 'L':['M -90 1810 C -220 2040 -245 2280 -115 2420 C -175 2380 -192 2280 -165 2170 C -150 2020 -65 1900 20 1810 Z',
      'M 250 1860 C 150 2050 70 2220 120 2330 C 135 2380 210 2430 208 2490 C 190 2435 100 2410 80 2340 C 42 2190 165 2000 250 1860 Z',
      'M -115 2300 C -90 2390 30 2425 70 2515 C 40 2470 -45 2450 -75 2420 C -110 2395 -130 2340 -115 2300 Z'],
 'R':['M 2100 1820 C 2190 2010 2250 2230 2100 2405 C 2165 2300 2165 2200 2135 2090 C 2105 1990 2060 1915 2010 1830 Z',
      'M 1780 1920 C 1900 2070 1970 2240 1920 2340 C 1890 2405 1825 2435 1820 2485 C 1835 2420 1880 2370 1885 2320 C 1900 2190 1850 2060 1780 1920 Z',
      'M 2110 2300 C 2100 2385 1995 2430 1970 2510 C 1975 2440 2040 2415 2070 2370 C 2090 2340 2100 2315 2110 2300 Z']}
 for path in shadow_paths[side]:
  m=path_mask(path)*np.clip((np.arange(H)[:,None]-1780)/190,0,1)*(out[:,:,3]>0)*.46
  out[:,:,:3]=np.rint(out[:,:,:3]*(1-m[:,:,None])+np.array([145,145,204])*m[:,:,None]).astype('uint8')
 # A pair of tapered curved interior strokes follows the two curls.
 stroke=Image.new('RGBA',(W,H));d=ImageDraw.Draw(stroke)
 paths=([(-110,1900),(-180,2080),(-160,2270),(-65,2390),(50,2420)],[(220,1930),(140,2100),(155,2260),(220,2390),(215,2470)]) if side=='L' else ([(1790,1920),(1900,2100),(1925,2270),(1870,2390)],[(2110,1900),(2220,2110),(2200,2280),(2110,2370),(2040,2390)])
 for points in paths:
  pts=np.array(points,float);tt=np.linspace(0,1,len(pts));qq=np.linspace(0,1,180);curve=np.stack([PchipInterpolator(tt,pts[:,k])(qq) for k in range(2)],axis=1)
  for i in range(len(curve)-1):
   fade=np.sin(np.pi*i/(len(curve)-1))**.6;width=max(1,round(4*fade));p0,p1=curve[i],curve[i+1];d.line((p0[0]+DX,p0[1],p1[0]+DX,p1[1]),fill=(106,107,160,round(125*fade)),width=width)
 s=np.array(stroke);s[out[:,:,3]==0]=0;out=combine(out,s);out[out[:,:,3]==0]=0
 return out

def recoat_root(a,key):
 """Repaint concealed occlusion cuts; smooth blend to the retained hair below."""
 ys,l,r,box=ROOTS[key];cov,u=band(ys,l,r);yy=np.arange(2048)[:,None]
 if key.startswith('Large'):
  # A flowing golden/pink cross-section, continuing the visible lower locks.
  pal=np.array([[246,222,175],[252,234,195],[246,220,181],[225,186,190],[250,229,187],[229,192,194]],float)
  if key=='Large_R':pal=pal[::-1].copy()
  colour=np.stack([np.interp(u,np.linspace(0,1,len(pal)),pal[:,k]) for k in range(3)],axis=2)
  # Below the old occlusion all original colour/line work is retained.
  t=np.clip((yy-1330)/260,0,1);t=t*t*(3-2*t);weight=(1-t)*(cov>.0)
  # Retain the outer true hair outline; replace only interior cut fragments.
  depth=cv2.distanceTransform((a[:,:,3]>127).astype('uint8'),cv2.DIST_L2,5)
  weight*=np.clip((depth-5)/24,0,1)
  out=a.copy();out[:,:,:3]=np.rint(a[:,:,:3]*(1-weight[:,:,None])+colour*weight[:,:,None]).clip(0,255).astype('uint8')
 else:
  # Paint the hidden inner root with a smooth strand-following profile. No
  # single-row donor extension: that would duplicate dark strokes as bands.
  xx=np.arange(2048)[None,:]
  gold=np.array([[249,230,189],[255,239,202],[247,228,191],[231,199,190]],float)
  blue=np.array([[170,181,222],[198,229,234],[187,219,233],[149,158,211]],float)
  if key=='Small_R':gold=gold[::-1].copy();blue=blue[::-1].copy()
  g=np.stack([np.interp(u,np.linspace(0,1,4),gold[:,k]) for k in range(3)],axis=2)
  b=np.stack([np.interp(u,np.linspace(0,1,4),blue[:,k]) for k in range(3)],axis=2)
  t=np.clip((yy-510)/270,0,1);t=t*t*(3-2*t);colour=g*(1-t[:,:,None])+b*t[:,:,None]
  if key=='Small_R':
   edge=PchipInterpolator([190,350,500,650,750,820],[1530,1555,1545,1530,1520,1510],extrapolate=True)(np.arange(2048))[:,None]
   inner=np.clip((edge-xx)/35+.5,0,1)
  else:
   edge=PchipInterpolator([210,350,500,650,740],[490,475,450,435,425],extrapolate=True)(np.arange(2048))[:,None]
   inner=np.clip((xx-edge)/25+.5,0,1)
  weight=np.maximum(inner,np.clip((570-yy)/100,0,1))*np.clip((830-yy)/80,0,1)
  depth=cv2.distanceTransform((a[:,:,3]>127).astype('uint8'),cv2.DIST_L2,5)
  weight*=np.clip((depth-3)/14,0,1)
  out=a.copy();out[:,:,:3]=np.rint(a[:,:,:3]*(1-weight[:,:,None])+colour*weight[:,:,None]).clip(0,255).astype('uint8')
 out[out[:,:,3]==0]=0
 return out

def repair_temple(a):
 # The old hidden backing ends in a horizontal step around y450. A single
 # connected Bézier silhouette follows the narrow temple lock into its tip.
 path='M 1140 120 C 1270 155 1410 250 1450 420 C 1460 505 1450 565 1465 650 C 1490 755 1510 830 1505 900 C 1490 980 1465 1030 1440 1050 C 1480 950 1480 880 1458 800 C 1420 665 1340 490 1280 350 C 1240 245 1180 155 1140 120 Z'
 cov=native(np.dstack([np.zeros((H,W,3),np.uint8),np.rint(path_mask(path)*255).astype('uint8')]))[:,:,3]/255
 # Replace a narrow root junction; preserve the long source lower curve.
 yy=np.arange(2048)[:,None];xx=np.arange(2048)[None,:]
 ys=[120,250,450,650,850,1050];le=[1140,1235,1320,1400,1460,1440];ri=[1141,1365,1455,1465,1505,1441]
 _,u=band(ys,le,ri);pal=np.array([[230,195,192],[250,231,187],[255,239,201],[225,184,190]])
 colour=np.stack([np.interp(u,np.linspace(0,1,len(pal)),pal[:,k]) for k in range(3)],axis=2)
 out=a.copy();region=(yy<650);t=np.clip((yy-480)/170,0,1);t=t*t*(3-2*t)
 back=np.dstack([np.rint(colour).astype('uint8'),np.rint(cov*253).astype('uint8')]);merged=combine(back,a)
 out[region[:,0]]=np.rint(back*(1-t[:,:,None])+merged*t[:,:,None]).astype('uint8')[region[:,0]]
 # Crop only the old root corners, not visible lower strand tips.
 out[(yy<600)&(cov==0)]=0;out[out[:,:,3]==0]=0
 return out

def repair_crown_seam(a):
 # Repaint only the artificial patch seam, not the dark original flow lines.
 out=a.copy();yy,xx=np.indices((2048,2048))
 edge=1302-(yy-200)*.64
 region=(yy>=200)&(yy<=350)&(xx>edge-14)&(a[:,:,3]>0)
 w=np.clip((xx-(edge-14))/22,0,1)*np.clip((yy-200)/25,0,1)*np.clip((350-yy)/20,0,1)
 # Local pale gold patch, matching its retained surrounding face-facing root.
 gold=np.array([249,234,199],float);out[region,:3]=np.rint(a[region,:3]*(1-w[region,None])+gold*w[region,None]).astype('uint8')
 return out

def alpha_polish(a):
 # Tiny isolated raster flecks at the old masks are not independent hair.
 out=a.copy();m=out[:,:,3]>127;c,labels,stats,_=cv2.connectedComponentsWithStats(m.astype('uint8'),8)
 dust=np.zeros(m.shape,bool)
 for i in range(1,c):
  if stats[i,cv2.CC_STAT_AREA]<=8:dust|=labels==i
 out[dust]=0
 # Pinholes along a contour union are filled from the same material only.
 m=out[:,:,3]>127;holes=binary_fill_holes(m)&~m
 if holes.any():
  idx=distance_transform_edt(~m,return_distances=False,return_indices=True);out[holes]=out[idx[0][holes],idx[1][holes]];out[holes,3]=253
 return out,{'isolated_opaque_fleck_pixels_removed':int(dust.sum()),'union_pinhole_pixels_filled':int(holes.sum())}

def finish_thin(a):
 # Small front lock also reached the old bottom edge. Continue its curl to a
 # pointed free end, retaining all original source pixels above the join.
 out=extended(a);path='M 1558 2000 C 1605 2028 1660 2025 1675 2008 C 1685 2065 1640 2115 1580 2120 C 1610 2100 1620 2075 1602 2062 C 1585 2055 1568 2040 1558 2000 Z'
 cov=path_mask(path);yy,xx=np.indices((H,W));u=np.clip((xx-DX-1560)/125,0,1)
 pal=np.array([[151,166,216],[202,233,231],[191,223,234],[154,165,208]])
 paint=np.dstack([np.stack([np.interp(u,np.linspace(0,1,4),pal[:,k]) for k in range(3)],axis=2).astype('uint8'),(cov*253).astype('uint8')]);paint[paint[:,:,3]==0]=0
 out=combine(paint,out);w=np.clip((yy-1995)/53,0,1)*((paint[:,:,3]>0)&(out[:,:,3]>0));out[:,:,:3]=np.rint(out[:,:,:3]*(1-w[:,:,None])+paint[:,:,:3]*w[:,:,None]).astype('uint8')
 return out

def smooth_holes(a):
 out=a.copy();m=a[:,:,3]>127;holes=binary_fill_holes(m)&~m
 if holes.any():
  idx=distance_transform_edt(~m,return_distances=False,return_indices=True);out[holes]=a[idx[0][holes],idx[1][holes]];out[holes,3]=253
 return out,int(holes.sum())

def prepare():
 for n in ['layers','qa','masks']:(OUT/n).mkdir(parents=True,exist_ok=True)
 source=PSDImage.open(SOURCE);ls={l.name:l for l in pixels(source)};parts={};records={}
 for key in ROOTS:
  a=full(ls[key+'_FullMaterial_LOCAL_REVIEW']);fixed,rec=repair_root(a,key);fixed=recoat_root(fixed,key)
  if key.startswith('Small'):fixed=small_cleanup(fixed,key);fixed,rec['filled_hole_pixels']=smooth_holes(fixed);parts[key]=extended(fixed)
  else:parts[key]=finish_large(fixed,key)
  parts[key],rec['alpha_polish']=alpha_polish(parts[key]);records[key]=rec;Image.fromarray(parts[key]).save(OUT/'layers'/(key+'.png'));print('Prepared',key,flush=True)
 # Latest front material candidates, never earlier superseded versions.
 mapping={'Crown':'CrownFringe_RightTipsRecovered_LOCAL_REVIEW','Cheek_L':'Cheek_L_UpperSurface_LOCAL_REVIEW','Cheek_R':'Cheek_R_ContinuousContour_LOCAL_REVIEW','Temple_R':'Temple_R_FullMaterial_LOCAL_REVIEW','Thin_R':'Thin_R_FullMaterial_LOCAL_REVIEW'}
 for key,name in mapping.items():
  a=full(ls[name]);a=repair_temple(a) if key=='Temple_R' else repair_crown_seam(a) if key=='Crown' else a;a,count=smooth_holes(a);parts[key]=finish_thin(a) if key=='Thin_R' else extended(a);records[key]={'filled_hole_pixels':count,'source':name}
  parts[key],records[key]['alpha_polish']=alpha_polish(parts[key]);Image.fromarray(parts[key]).save(OUT/'layers'/(key+'.png'))
 # Original non-hair layers remain independent, unwarped and in native positions.
 for n in ['Body_Visible','Neck_Visible','FacePaint_AfterCheekRecovery_SOURCE','Ear_Near_ImageRight','Flower_ImageLeft','Flower_ImageRight','Eyebrow_L_Full_LOCAL_CLEANUP','Eyebrow_R_Full_LOCAL_CLEANUP','Fringe_R_Context_AfterTipRecovery_SOURCE','Left_FringeCheek_SkinContext_SOURCE']:
  parts[n]=extended(full(ls[n]));Image.fromarray(parts[n]).save(OUT/'layers'/(n+'.png'))
 # Flower contour fragments in the old residual layer belong to the accessory.
 residual=full(ls['Boundary_Review_NOT_RIG_READY']);yy,xx=np.indices((2048,2048))
 for side,lo,hi in [('Left',350,850),('Right',1200,1700)]:
  fragment=residual.copy();fragment[~((yy<220)&(xx>lo)&(xx<hi))]=0
  name='Flower_Image'+side;parts[name]=combine(parts[name],extended(fragment));Image.fromarray(parts[name]).save(OUT/'layers'/(name+'.png'))
 for l in pixels(next(g for g in source if g.name=='03_Local_foreground_bangs')):
  if l.visible:
   parts[l.name]=extended(full(l));Image.fromarray(parts[l.name]).save(OUT/'layers'/(l.name+'.png'))
 for state in ['Open','Half','Closed']:
  for l in pixels(next(g for g in source if g.name=='02_'+state)):
   parts[l.name]=extended(full(l));Image.fromarray(parts[l.name]).save(OUT/'layers'/(l.name+'.png'))
 # Restore a few source boundary pixels that were held in historical mixed
 # context layers. This is source recovery, separate from inferred hair paint.
 inputs=OUT/'inputs';inputs.mkdir(exist_ok=True)
 context_path=inputs/'source-context-reference.png'
 if not context_path.exists():
  old=PSDImage.open(TURN/'side_blink_refinement/left/Rurino_Turn_Left_Blink_Materials_v034.psd')
  layer=next(l for l in pixels(old) if l.name=='Context_Skin_Reference');Image.fromarray(full(layer)).save(context_path)
 original=np.array(Image.open(context_path).convert('RGBA'))
 # Recover visible original root strokes instead of leaving the old diagonal
 # reconstruction patch across them. Trace the shared root, excluding flowers.
 rootpath='M 1100 110 C 1200 105 1300 140 1360 215 C 1400 290 1480 405 1490 500 C 1450 570 1390 600 1370 575 C 1320 460 1250 390 1190 350 C 1140 270 1090 200 1100 110 Z'
 rootcov=path_mask(rootpath)[:2048,DX:DX+2048]
 flower=native(parts['Flower_ImageRight'])[:,:,3]>64
 flower=cv2.dilate(flower.astype('uint8'),np.ones((3,3),np.uint8)).astype(bool)
 rootcov[flower|(original[:,:,3]<220)]=0
 patch=original.copy();patch[:,:,3]=np.rint(patch[:,:,3]*rootcov).astype('uint8');patch[patch[:,:,3]==0]=0
 parts['Crown']=combine(parts['Crown'],extended(patch));parts['Crown'],polish=alpha_polish(parts['Crown'])
 Image.fromarray(parts['Crown']).save(OUT/'layers/Crown.png')
 records['Crown']['visible_original_root_recovery_pixels']=int((patch[:,:,3]>0).sum());records['Crown']['post_recovery_alpha_polish']=polish
 composed=native(assembly(parts));m=composed[:,:,3]>127;holes=binary_fill_holes(m)&~m
 yy,xx=np.indices((2048,2048));recover=holes&(original[:,:,3]>220)
 regions={'Small_L':recover&(xx<550)&(yy>700)&(yy<1000),
          'Face_Boundary_Underlap_SOURCE':recover&(((xx>1100)&(xx<1250)&(yy>800)&(yy<1120))|((xx>550)&(xx<1300)&(yy>=1120)&(yy<1320)))}
 for name,hit in regions.items():
  patch=np.zeros_like(original);patch[hit]=original[hit]
  parts[name]=combine(extended(patch),parts[name]) if name in parts else extended(patch)
  Image.fromarray(parts[name]).save(OUT/'layers'/(name+'.png'))
  records.setdefault(name,{})['original_boundary_pixels_recovered']=int(hit.sum())
 records['source_context_reference']={'png_sha256':sha(context_path),'source_layer':'Context_Skin_Reference','use':'only missing original boundary pixels; not a flattened head replacement'}
 (OUT/'preparation.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n')
 preview(parts)
 return parts,records
ORDER=['Large_L','Large_R','Small_L','Small_R','Body_Visible','Neck_Visible','Thin_R','Fringe_R_Context_AfterTipRecovery_SOURCE','Left_FringeCheek_SkinContext_SOURCE','Face_Boundary_Underlap_SOURCE','FacePaint_AfterCheekRecovery_SOURCE','Ear_Near_ImageRight','Temple_R','Cheek_L','Cheek_R','Crown','Flower_ImageLeft','Flower_ImageRight']
def assembly(parts,state='Open'):
 im=Image.new('RGBA',(W,H))
 for n in ORDER:
  if n in parts:im.alpha_composite(Image.fromarray(parts[n]))
 for side in ['Far','Near']:
  white=parts.get(state+'_'+side+'_White');iris=parts.get(state+'_'+side+'_Iris')
  if white is not None:
   eye=Image.fromarray(white)
   if iris is not None:
    ir=iris.copy();ir[:,:,3]=np.rint(ir[:,:,3].astype(float)*white[:,:,3]/255).astype('uint8');eye.alpha_composite(Image.fromarray(ir))
   im.alpha_composite(eye)
  for part in ['UpperLid','LowerLid']:
   a=parts.get(state+'_'+side+'_'+part)
   if a is not None:im.alpha_composite(Image.fromarray(a))
 for n in ['Left_Cheek_EyeOverlap_SOURCE','Left_Fringe_EyeOverlap_SOURCE','RightFringe_ForegroundTips_SOURCE','Eyebrow_L_Full_LOCAL_CLEANUP','Eyebrow_R_Full_LOCAL_CLEANUP']:
  if n in parts:im.alpha_composite(Image.fromarray(parts[n]))
 return np.array(im)
def preview(parts):
 font=ImageFont.truetype(FONT,22)
 for state in ['Open','Half','Closed']:
  a=assembly(parts,state);Image.fromarray(a).save(OUT/'qa'/('assembled-'+state+'.png'))
 a=Image.open(OUT/'qa/assembled-Open.png');bg=checker((1000,815));im=a.copy();im.thumbnail(bg.size);bg.paste(im,((1000-im.width)//2,0),im);bg.save(OUT/'qa/whole-hair-assembly.jpg',quality=96)
 sheet=Image.new('RGB',(1440,1680),'#e8edf3');d=ImageDraw.Draw(sheet)
 for i,n in enumerate(['Small_L','Small_R','Large_L','Large_R','Crown','Temple_R']):
  im=Image.fromarray(parts[n]);box=im.getbbox();im=im.crop(box);im.thumbnail((690,490));bg=checker((700,490));bg.paste(im,((700-im.width)//2,(490-im.height)//2),im);x=i%2*720;y=i//2*560;sheet.paste(bg,(x+10,y+50));d.text((x+15,y+15),n+' · 实际独立素材',font=font,fill='#26394c')
 sheet.save(OUT/'qa/whole-hair-components.jpg',quality=96)
if __name__=='__main__':prepare()
