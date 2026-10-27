"""Side-eye edge cleanup and side blink material keyforms; no Cubism rig.

Original irises stay fixed in pixel scale. Local LibTV blink drawings provide
lid contours; the rest of the head is protected and never warped.
"""
import gc,hashlib,json
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFilter
from scipy.ndimage import distance_transform_edt,gaussian_filter1d,binary_fill_holes
from psd_tools import PSDImage
from psd_tools.api.layers import Group,PixelLayer

ROOT=Path(__file__).resolve().parents[1]
TURN=ROOT/'rebuild_v3_4/turn_redraw';OLD=TURN/'eye_layers';OUT=TURN/'side_blink_refinement'
# Coordinates in the existing 768 x 384 eye band. Only mattes are refined;
# these ellipses never resample the original iris RGB texture.
CFG={
 'left':{'Far':{'ellipse':(172,181,51,70,0),'region':[(73,108),(125,73),(195,80),(245,116),(259,180),(229,242),(187,260),(126,259),(91,224)],'split':230},
         'Near':{'ellipse':(529,180,66,71,-3),'region':[(410,129),(455,84),(517,67),(590,74),(647,112),(698,130),(697,190),(634,238),(566,259),(468,259),(424,209)],'split':233}},
 'right':{'Near':{'ellipse':(237,174,66,70,5),'region':[(78,118),(142,79),(206,66),(280,74),(331,104),(349,175),(303,226),(272,255),(175,257),(113,228),(77,185)],'split':228},
          'Far':{'ellipse':(591,187,57,67,6),'region':[(493,137),(537,95),(592,77),(648,94),(687,129),(698,192),(667,240),(622,269),(549,264),(507,231)],'split':239}}
}
SIZE=(768,384)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save_json(p,v):p.write_text(json.dumps(v,indent=2,ensure_ascii=False)+'\n')
def polygon(points):
 m=Image.new('L',(SIZE[0]*4,SIZE[1]*4));ImageDraw.Draw(m).polygon([(x*4,y*4) for x,y in points],fill=255)
 return np.array(m.resize(SIZE,Image.Resampling.LANCZOS))
def clean_components(mask,min_area=12):
 n,l,s,_=cv2.connectedComponentsWithStats(mask.astype('uint8'));return np.isin(l,[i for i in range(1,n) if s[i,4]>=min_area])
def image(rgb,alpha):
 a=np.dstack([rgb,np.uint8(np.clip(np.rint(alpha),0,255))]);a[a[:,:,3]==0]=0;return Image.fromarray(a.astype('uint8'))
def nearest_rgb(rgb,valid):
 assert valid.any();idx=distance_transform_edt(~valid,return_distances=False,return_indices=True);return rgb[idx[0],idx[1]]
def extract_ink(rgb,region,hair,exclude=None):
 """Keep connected dark ink, not original-to-skin residual fragments."""
 dark=(rgb.max(2)<205)&(region>128)&(hair<100)
 if exclude is not None:dark &= ~exclude
 dark=clean_components(dark,14)
 support=cv2.dilate(dark.astype('uint8'),np.ones((3,3),np.uint8))>0
 # Continuous opacity based on contrast to a locally extrapolated ink colour.
 solid=clean_components((rgb.max(2)<130)&dark,6)
 ink=nearest_rgb(rgb,solid)
 # White/skin around an outline has luminance > 210. Estimate coverage using
 # the darkest channel, keeping the original opaque line RGB exactly.
 coverage=np.clip((236-rgb.min(2).astype('float32'))/np.maximum(236-ink.min(2),1),0,1)
 coverage[dark]=1;coverage*=support;coverage*=region/255;coverage*=1-hair/255
 if exclude is not None:coverage*=~exclude
 result=ink.copy();result[dark]=rgb[dark]
 return image(result,coverage*255)
def composite_eye(parts,gaze=(0,0)):
 white=np.array(parts['White']);moving=Image.new('RGBA',SIZE);moving.alpha_composite(parts['Iris'],gaze)
 a=np.array(moving);f=a[:,:,3:4]/255;white[:,:,:3]=np.rint(a[:,:,:3]*f+white[:,:,:3]*(1-f))
 result=Image.fromarray(white);result.alpha_composite(parts['UpperLid']);result.alpha_composite(parts['LowerLid']);return result

def prepare_side(side,record):
 dest=OUT/side
 for n in ['layers','masks','qa']:(dest/n).mkdir(parents=True,exist_ok=True)
 original=Image.open(TURN/record['source']).convert('RGBA');box=record['crop_xyxy'];rgb=np.array(original.crop(box))[:,:,:3]
 skin=np.array(Image.open(OLD/side/'qa/skin-plate-clean.png').convert('RGB'))
 whiteplate=np.array(Image.open(OLD/'sources'/f'{side}-white-generated.png').convert('RGB').resize(SIZE,Image.Resampling.LANCZOS))
 # Trace the actual bang/cheek-lock silhouettes. The old warm-colour mask
 # captured dark eyelash islands, which become visible when the eyes close.
 hair_polygons={
 'left':[
  [(0,0),(70,0),(73,115),(77,168),(87,212),(101,247),(120,285),(140,327),(0,384)],
  [(77,0),(148,0),(133,61),(127,92),(126,131),(105,105),(92,81)],
  [(450,0),(487,0),(478,60),(460,102),(434,140),(444,104),(452,61)],
  [(574,0),(637,0),(617,54),(601,89),(581,119),(585,80)],
  [(629,0),(679,0),(662,63),(645,111),(625,143),(631,106)],
  [(725,0),(768,0),(768,384),(643,281),(666,242),(685,211),(699,166),(710,102)]],
 'right':[
  [(0,0),(75,0),(77,161),(90,210),(113,247),(143,279),(0,384)],
  [(84,0),(222,0),(174,116),(154,96),(143,84),(130,57)],
  [(511,0),(551,0),(536,69),(522,105),(506,132),(495,143),(508,106),(514,60)],
  [(625,0),(677,0),(662,76),(643,124),(642,91)],
  [(673,0),(711,0),(698,80),(680,126),(672,145),(677,104)],
  [(735,0),(768,0),(768,384),(667,285),(684,248),(694,206),(706,159),(719,94)]]}
 hair=np.maximum.reduce([polygon(points) for points in hair_polygons[side]])
 # Keep dark hair outlines only within two pixels of the actual light hair.
 # This discards black lash wedges accidentally enclosed by a traced tip.
 light=(rgb.max(2)>150)&(hair>128)
 support=cv2.dilate(light.astype('uint8'),np.ones((3,3),np.uint8))
 hair=hair*support
 # At the original bang/lash contact, old lash ink is not a hair outline.
 # The existing LibTV skin plate retains the underlying tapered hair tip.
 tip_boxes={'left':[(103,100,132,145),(578,94,644,151)],
            'right':[(142,83,192,122),(636,100,681,150)]}
 for x,y,r,b in tip_boxes[side]:
  patch=hair[y:b,x:r];patch[rgb[y:b,x:r].max(2)<150]=0
 hairim=image(rgb,hair)

 clean={};regions=[];reports=[]
 for name,cfg in CFG[side].items():
  region=polygon(cfg['region']);regions.append(region)
  cx,cy,rx,ry,angle=cfg['ellipse'];ellipse=np.zeros((384,768),np.uint8)
  cv2.ellipse(ellipse,((cx,cy),(2*rx,2*ry),angle),255,-1,cv2.LINE_AA)
  aperture=np.array(Image.open(OLD/side/'masks'/f'{name}_Opening.png').filter(ImageFilter.GaussianBlur(.55)))
  # Derive visible boundaries from the original coloured disk and dark rim;
  # do not carry the white crescent attached to the older ellipse selection.
  v=rgb.astype('int16');red,green,blue=v.transpose(2,0,1)
  seed=(ellipse>100)&(aperture>200)&(((green-red>8)&(blue-red>-12))|(rgb.max(2)<140))
  seed=clean_components(seed,100)
  seed=binary_fill_holes(cv2.morphologyEx(seed.astype('uint8'),cv2.MORPH_CLOSE,np.ones((3,3),np.uint8)))
  # Fill hidden top/bottom margins only, using nearest genuine iris pixels.
  hidden=(ellipse>100)&(aperture<100)
  support=(seed|hidden).astype('uint8')
  pts=cv2.findNonZero(support);disk=np.zeros_like(support);cv2.fillConvexPoly(disk,cv2.convexHull(pts),1);disk=disk>0
  alpha=np.array(Image.fromarray(disk.astype('uint8')*255).filter(ImageFilter.GaussianBlur(.6)))
  valid=(cv2.erode(disk.astype('uint8'),np.ones((5,5),np.uint8))>0)&(aperture>240)
  irgb=nearest_rgb(rgb,valid);irgb[valid]=rgb[valid]
  # Visible dark rim continues into antialiased boundary pixels. Avoid copying
  # near-white source antialias fringe into an opaque moving iris.
  edge=(alpha>0)&~(cv2.erode(disk.astype('uint8'),np.ones((5,5),np.uint8))>0)
  darkrim=seed&(rgb.max(2)<140)
  ink=nearest_rgb(rgb,darkrim);irgb[edge]=ink[edge]
  iris=image(irgb,alpha)
  # Ink immediately above/below the eye opening belongs to eyelids, not iris.
  exclude=aperture>16  # no original iris/shadow specks in the new white aperture
  lids=extract_ink(rgb,region,hair,exclude)
  la=np.array(lids);yy=np.arange(384)[:,None]
  upper=la.copy();upper[yy.repeat(768,axis=1)>=cfg['split']]=0
  lower=la.copy();lower[yy.repeat(768,axis=1)<cfg['split']]=0
  clean[name]={'White':image(whiteplate,aperture),'Iris':iris,'UpperLid':Image.fromarray(upper),'LowerLid':Image.fromarray(lower)}
  Image.fromarray(region).save(dest/'masks'/f'{name}_Region.png')
  Image.fromarray(ellipse).save(dest/'masks'/f'{name}_Iris.png')
  reports.append({'eye':name,'iris_rgb_preserved_pixels':int(valid.sum()),'iris_texture_scaled':False})
 # Replace the whole eye feature region with clean skin, with a soft local seam.
 union=np.maximum.reduce(regions);union=cv2.dilate(union,np.ones((17,17),np.uint8));union=np.array(Image.fromarray(union).filter(ImageFilter.GaussianBlur(3)))
 raw_union=union.copy();union=np.minimum(union,255-hair)
 band=np.array(original.crop(box));f=union[:,:,None]/255
 band[:,:,:3]=np.rint(skin*f+rgb*(1-f))
 # Split source alpha between context and foreground without doubling it.
 hm=hair.astype('float32')*raw_union/65025;aa=band[:,:,3]/255
 foreground_alpha=aa*hm
 band[:,:,3]=np.rint(255*aa*(1-hm)/np.maximum(1-foreground_alpha,1/65536))
 hairim=image(rgb,foreground_alpha*255)
 context=original.copy();context.paste(Image.fromarray(band),(box[0],box[1]))
 context.save(dest/'layers/Context_Skin_Reference.png');hairim.save(dest/'layers/Foreground_Hair_Overlap.png')
 Image.fromarray(raw_union).save(dest/'masks/Editable_Region.png')
 for n,p in clean.items():
  for part,im in p.items():im.save(dest/'layers'/f'Open_{n}_{part}.png')
 def render(parts=clean,gaze=(0,0)):
  im=context.copy();band=Image.new('RGBA',SIZE)
  for n,p in parts.items():band.alpha_composite(composite_eye(p,gaze))
  band.alpha_composite(hairim);im.alpha_composite(band,(box[0],box[1]));return im
 render().save(dest/'qa/open-clean.png')
 for i,g in enumerate([(-6,0),(0,0),(6,0),(0,-4),(0,4)]):render(gaze=g).crop(box).save(dest/'qa'/f'clean-gaze-{i}.png')
 sheet=Image.new('RGB',(1200,480),(43,48,61));draw=ImageDraw.Draw(sheet)
 for row,(n,p) in enumerate(clean.items()):
  for col,(part,im) in enumerate(p.items()):
   tile=im.crop(im.getbbox());tile.thumbnail((270,180));sheet.paste(tile,(col*300+(300-tile.width)//2,row*240+40),tile);draw.text((col*300+8,row*240+8),n+' '+part,fill='white')
 sheet.save(dest/'qa/clean-layers.jpg',quality=96)
 return {'side':side,'source_sha256':sha(TURN/record['source']),'eyes':reports},clean,context,hairim

HALF_EDGE={
 ('left','Far'):[(104,218),(110,177),(122,157),(150,155),(180,158),(214,163),(237,172),(250,180)],
 ('left','Near'):[(435,178),(464,163),(500,158),(545,157),(580,158),(615,164),(648,177),(653,189)],
 ('right','Near'):[(113,206),(117,168),(128,155),(157,151),(195,153),(238,157),(280,161),(314,164),(342,178)],
 ('right','Far'):[(502,187),(528,176),(551,174),(580,174),(620,174),(647,176),(675,183),(675,195)]}

def main_component(im):
 a=np.array(im);mask=a[:,:,3]>100;n,l,stats,_=cv2.connectedComponentsWithStats(mask.astype('uint8'))
 selected=l==(1+np.argmax(stats[1:,4]));selected=cv2.dilate(selected.astype('uint8'),np.ones((3,3),np.uint8))
 main=a.copy();main[:,:,3]*=selected;rest=a.copy();rest[:,:,3]*=1-selected
 return Image.fromarray(main),Image.fromarray(rest)

def make_keyforms(side,clean,hairim):
 hair=np.array(hairim)[:,:,3];keys={'Open':clean};yy=np.arange(384)[:,None];xx=np.arange(768)
 for state in ['Half','Closed']:
  generated=np.array(Image.open(OUT/'sources'/f'{side}-{state.lower()}-generated.png').convert('RGB').resize(SIZE,Image.Resampling.LANCZOS))
  parts={}
  for n,cfg in CFG[side].items():
   region=polygon(cfg['region'])
   # Bangs divide an upper lash into multiple disconnected pieces. Those pieces
   # must NOT be mistaken for the eyelid crease and translated down the face.
   folds={('left','Far'):[(134,72),(177,75),(216,88),(247,119),(220,103),(175,88),(138,82)],
          ('left','Near'):[(443,106),(466,82),(505,71),(554,70),(569,78),(520,79),(478,92),(450,112)],
          ('right','Near'):[(208,69),(248,67),(289,76),(326,98),(341,118),(309,97),(270,83),(228,78)],
          ('right','Far'):[(520,114),(545,89),(575,81),(620,85),(604,94),(573,91),(546,105),(525,122)]}
   ca=np.array(clean[n]['UpperLid']);
   if (side,n)==('left','Near'):ca[:,:,3]=np.rint(ca[:,:,3]*np.clip((np.arange(768)[None,:]-458)/9,0,1))
   if (side,n)==('right','Far'):ca[:,:,3]=np.rint(ca[:,:,3]*np.clip((np.arange(768)[None,:]-540)/9,0,1))
   ca[:,:,3]=np.rint(ca[:,:,3]*(polygon(folds[(side,n)])/255));crease=Image.fromarray(ca)
   if state=='Half':
    points=HALF_EDGE[(side,n)]
    # Restrict the cutoff to the central iris only when extracting the lash;
    # full outer-wing ink remains. Aperture uses the lower lid edge envelope.
    points=sorted(points);line=np.interp(xx,[p[0] for p in points],[p[1] for p in points])
    cx,cy,rx,ry,angle=cfg['ellipse']
    exclusion=(yy>line[None,:]+1)&(xx[None,:]>cx-rx-3)&(xx[None,:]<cx+rx+3)
    lower_limit=cfg['split']-3
    local_region=region.copy();local_region[lower_limit:]=0
    # Do not include generated folds; keep one original fold above the lid.
    local_region[:115 if side=='left' else 113]=0
    upper=extract_ink(generated,local_region,hair,exclusion);upper,_=main_component(upper)
    white=np.array(clean[n]['White']);white[:,:,3]=np.rint(white[:,:,3]*np.clip(yy-line[None,:]+.5,0,1))
    white=Image.fromarray(white);lower=clean[n]['LowerLid'].copy();fold_shift=20
   else:
    local_region=region.copy();local_region[:153]=0
    upper=extract_ink(generated,local_region,hair);upper,_=main_component(upper)
    white=Image.new('RGBA',SIZE);lower=Image.new('RGBA',SIZE);fold_shift=38
   # The fold is a separate original-ink component, moved locally with the lid.
   moved=Image.new('RGBA',SIZE);moved.alpha_composite(crease,(0,fold_shift));upper.alpha_composite(moved)
   parts[n]={'White':white,'Iris':clean[n]['Iris'].copy(),'UpperLid':upper,'LowerLid':lower}
  keys[state]=parts
 return keys

def render_full(context,hairim,parts,box,gaze=(0,0)):
 im=context.copy();band=Image.new('RGBA',SIZE)
 for n,p in parts.items():band.alpha_composite(composite_eye(p,gaze))
 band.alpha_composite(hairim);im.alpha_composite(band,(box[0],box[1]));return im

def save_keyforms(side,keys,context,hairim,box):
 dest=OUT/side;sheet=Image.new('RGB',(768,3*410),(225,229,237));draw=ImageDraw.Draw(sheet)
 for row,(state,parts) in enumerate(keys.items()):
  for n,p in parts.items():
   for part,im in p.items():im.save(dest/'layers'/f'{state}_{n}_{part}.png')
  frame=render_full(context,hairim,parts,box);frame.save(dest/'qa'/f'{state.lower()}-keyform.png');tile=frame.crop(box)
  sheet.paste(tile,(0,row*410+24),tile);draw.text((8,row*410+6),f'{side.upper()} / {state.upper()} - material keyform',fill=(40,45,60))
 sheet.save(dest/'qa/keyforms.jpg',quality=96)


def put_layer(psd,parent,name,im,offset=(0,0),clip=False):
 bounds=im.getbbox()
 if not bounds:return None
 l=PixelLayer.frompil(im.crop(bounds),psd_file=psd,layer_name=name,left=offset[0]+bounds[0],top=offset[1]+bounds[1])
 parent.append(l);l.clipping_layer=clip;return l

def export_psd(side,keys,context,hairim,box):
 dest=OUT/side;psd=PSDImage.new('RGBA',(2048,2048),color=0)
 g=Group.new('01_Context_NOT_complete_head_split',parent=psd);put_layer(psd,g,'Context_Skin_Reference',context)
 manifest=[]
 for state,parts in keys.items():
  state_group=Group.new('02_'+state,parent=psd);state_group.visible=state=='Open'
  for n,p in parts.items():
   eye_group=Group.new(state+'_'+n,parent=state_group)
   for part,im in p.items():
    if state=='Closed' and part!='UpperLid':continue
    name=state+'_'+n+'_'+part
    layer=put_layer(psd,eye_group,name,im,(box[0],box[1]),part=='Iris')
    if layer:manifest.append({'name':name,'file':'layers/'+name+'.png','offset':box[:2],'state':state,'clip_to':name.replace('_Iris','_White') if part=='Iris' else None})
 g=Group.new('03_Local_foreground_bangs',parent=psd);put_layer(psd,g,'Foreground_Hair_Overlap',hairim,(box[0],box[1]))
 path=dest/f'Rurino_Turn_{side.title()}_Blink_Materials_v034.psd';psd.save(path);del psd;gc.collect()
 save_json(dest/'manifest.json',{'canvas':[2048,2048],'crop_xyxy':box,'default':'Open','keyform_control':'Show exactly one of 02_Open, 02_Half, 02_Closed. Closed contains lids only.',
 'layers':[{'name':'Context_Skin_Reference','file':'layers/Context_Skin_Reference.png','offset':[0,0]}]+manifest+[{'name':'Foreground_Hair_Overlap','file':'layers/Foreground_Hair_Overlap.png','offset':box[:2]}],
 'limitations':'material keyforms only; no continuous blink/head-turn rig, no mesh or runtime export'})
 return path

def main():
 records=json.loads((OLD/'source-crops.json').read_text());reports=[]
 for side,record in records.items():
  report,clean,context,hairim=prepare_side(side,record)
  keys=make_keyforms(side,clean,hairim);save_keyforms(side,keys,context,hairim,record['crop_xyxy'])
  path=export_psd(side,keys,context,hairim,record['crop_xyxy']);report['psd_sha256']=sha(path)
  reports.append(report);gc.collect()
 save_json(OUT/'cleanup-checks.json',reports)
 print(json.dumps(reports,indent=2))
if __name__=='__main__':main()
