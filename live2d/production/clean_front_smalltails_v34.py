"""Remove flower ghosts, pink under-layer fragments and broken small-tail tips.
Uses historical registered artwork; does not infer or bind animation.
"""
from pathlib import Path
import gc,json,hashlib,shutil,cv2,numpy as np
from PIL import Image,ImageDraw
from restore_front_neutral_v34 import path_alpha
from complete_front_smalltails_v34 import contour,compose
from psd_tools import PSDImage
from psd_tools.api.layers import Group,PixelLayer
p=Path(__file__).resolve().parents[1]/'rebuild_v3_4';out=p/'front_smalltails_clean'
for folder in ['colour','ink','layers','qa','qa-runtime','runtime','runtime-reexport']:(out/folder).mkdir(parents=True,exist_ok=True)
records=[]
raw=np.array(Image.open(p/'underpaint/backhair-underpaint-raw.png').convert('RGBA'))
CUT={
'L':'M 100 100 L 800 100 L 800 930 L 600 930 L 600 1036 L 539 1036 C 501 1018 466 987 440 952 Q 456 985 478 1004 C 452 996 431 985 418 976 C 378 948 349 897 335 844 L 350 1080 L 100 1080 Z',
'R':'M 1200 100 L 1950 100 L 1950 1080 L 1680 1080 L 1699 844 C 1682 910 1652 956 1623 980 Q 1596 998 1573 1005 Q 1593 984 1608 951 C 1576 990 1541 1018 1499 1034 L 1450 1034 L 1450 930 L 1200 930 Z'}
sheet=Image.new('RGB',(1500,1100),'#f7f7f7');d=ImageDraw.Draw(sheet)
for j,s in enumerate('LR'):
 a=np.array(Image.open(p/'front_smalltails/colour'/f'SideHair_{s}.png').convert('RGBA'));old=a.copy()
 # Replace the ghost flower seams from matching, registered root artwork.
 weight=np.clip((640-np.arange(2048))/100,0,1)[:,None,None]
 a[:,:,:3]=np.rint(a[:,:,:3]*(1-weight)+raw[:,:,:3]*weight).astype('uint8')
 # Trace the blue strands at the lowest split; discard the pink under-layer.
 cut=path_alpha(CUT[s],(0,0,2048,2048))
 if s=='L':cut[:,:400]=255
 else:cut[:,1640:]=255
 repairpath = ('M 463 875 Q 498 976 539 1036 C 501 1018 466 987 440 952 Q 456 985 478 1004 C 452 996 431 985 418 976 C 378 948 349 897 335 844 L 335 780 L 463 780 Z' if s=='L' else 'M 1548 874 C 1550 923 1528 984 1499 1034 C 1541 1018 1576 990 1608 951 Q 1593 984 1573 1005 C 1660 965 1685 900 1699 844 L 1699 800 L 1548 800 Z')
 patch=path_alpha(repairpath,(0,0,2048,2048));missing=np.maximum(patch.astype('int16')-a[:,:,3],0)/255
 a[:,:,:3]=np.rint(a[:,:,:3]*(1-missing[:,:,None])+raw[:,:,:3]*missing[:,:,None]).astype('uint8')
 a[:,:,3]=np.minimum(np.maximum(a[:,:,3],patch),cut)
 # Replace the broken terminal contour itself, rather than intersecting it
 # with the old stepped cutout and retaining its notches.
 xx0,xx1=(350,600) if s=='L' else (1450,1699)
 w=np.clip((np.arange(940,1100)-940)/20,0,1)[:,None]
 a[940:1100,xx0:xx1,3]=np.rint(a[940:1100,xx0:xx1,3]*(1-w)+patch[940:1100,xx0:xx1]*w).astype('uint8')
 if s=='R':
  w=np.clip((np.arange(840,1000)-880)/40,0,1)[:,None]
  a[840:1000,1595:1699,3]=np.rint(a[840:1000,1595:1699,3]*(1-w)+patch[840:1000,1595:1699]*w).astype('uint8')
 # Retain only the connected hair body, including its antialiased boundary.
 n,lab,stats,_=cv2.connectedComponentsWithStats((a[:,:,3]>10).astype('uint8'),8);main=1+np.argmax(stats[1:,-1]);keep=cv2.dilate((lab==main).astype('uint8'),np.ones((3,3),np.uint8));a[:,:,3]*=keep
 # Pink slivers between blue tips are background contamination. Confine repair
 # to the lower blue portion; do not desaturate the pink-to-yellow root shading.
 rgb=a[:,:,:3].astype('int16');yy=np.indices(a.shape[:2])[0]
 pink=(yy>740)&(a[:,:,3]>0)&(rgb[:,:,0]>rgb[:,:,2]+3)&(rgb[:,:,0]>rgb[:,:,1]+15)
 mask=cv2.dilate(pink.astype('uint8'),np.ones((13,13),np.uint8))*255
 if s=='R':
  cv2.polylines(mask,[np.array([[1549,890],[1548,912],[1545,932],[1540,947]],np.int32)],False,255,14)
 # Pad outside with nearest opaque colours so inpainting cannot sample black.
 valid=(a[:,:,3]>200).astype('uint8');_,labels=cv2.distanceTransformWithLabels(1-valid,cv2.DIST_L2,5,labelType=cv2.DIST_LABEL_PIXEL)
 palette=a[:,:,:3][valid>0];pad=palette[np.maximum(labels-1,0)]
 repaired=cv2.inpaint(pad,mask,9,cv2.INPAINT_TELEA)
 blend=cv2.GaussianBlur(mask,(5,5),0)/255;blend*=a[:,:,3]>0
 a[:,:,:3]=np.rint(a[:,:,:3]*(1-blend[:,:,None])+repaired*blend[:,:,None]).astype('uint8');a[a[:,:,3]==0]=0
 # Remove the old baked edge colour before drawing the separate contour.
 # In particular, antialiased pink pixels must not survive on a dark backdrop.
 depth=cv2.distanceTransform((a[:,:,3]>220).astype('uint8'),cv2.DIST_L2,5)
 safe=((a[:,:,3]>240)&(depth>=4)).astype('uint8')
 _,edge_labels=cv2.distanceTransformWithLabels(1-safe,cv2.DIST_L2,5,labelType=cv2.DIST_LABEL_PIXEL)
 safe_rgb=a[:,:,:3][safe>0];edge_rgb=safe_rgb[np.maximum(edge_labels-1,0)]
 edge=(a[:,:,3]>0)&(depth<3.5)&(mask>0);a[:,:,:3][edge]=edge_rgb[edge]
 im=Image.fromarray(a);ink=contour(im);im.save(out/'colour'/f'SideHair_{s}.png');ink.save(out/'ink'/f'Ink_SideHair_{s}.png')
 records.append({'side':s,'pink_pixels_targeted':int(pink.sum()),'removed_opaque_pixels':int(((old[:,:,3]>30)&(a[:,:,3]<=30)).sum())})
 im=Image.alpha_composite(im,ink);box=(150,170,750,1055) if s=='L' else (1290,170,1890,1055);tile=im.crop(box).resize((720,1062));sheet.paste(tile,(j*750,25),tile);d.text((j*750+5,5),s,fill='black');print(s,'pink',int(pink.sum()),'removed',int(((old[:,:,3]>30)&(a[:,:,3]<=30)).sum()))
sheet.save(out/'qa/clean-smalltails-isolated.png')
source=p/'front_smalltails';manifest=json.loads((source/'manifest.json').read_text());groups=manifest['groups']
parts={r['name']:Image.open(source/r['file']).convert('RGBA') for r in manifest['layers']}
oldparts={k:v.copy() for k,v in parts.items()}
for s in 'LR':
 for prefix,folder in [('', 'colour'),('Ink_', 'ink')]:
  name=prefix+'SideHair_'+s;parts[name]=Image.open(out/folder/f'{name}.png').convert('RGBA')
# Detailed material checks on both light and dark backgrounds.
sheet=Image.new('RGB',(1600,1060),'#dedede');d=ImageDraw.Draw(sheet)
for col,s in enumerate('LR'):
 name='SideHair_'+s;box=(150,730,750,1070) if s=='L' else (1290,730,1890,1070)
 for row,partset in enumerate([oldparts,parts]):
  tile=Image.alpha_composite(partset[name],partset['Ink_'+name]).crop(box).resize((800,453))
  bg=Image.new('RGB',tile.size,'#ffffff' if row==0 else '#344050');bg.paste(tile,(0,0),tile)
  sheet.paste(bg,(col*800,row*530+40));d.text((col*800+12,row*530+12),s+(' / BEFORE' if row==0 else ' / CLEANED'),fill='black')
sheet.save(out/'qa/smalltails-cleanup-closeup.jpg',quality=97)
# Both backgrounds for the final material, so edge problems cannot hide.
sheet=Image.new('RGB',(1600,1000),'#ddd');d=ImageDraw.Draw(sheet)
for col,s in enumerate('LR'):
 name='SideHair_'+s;im=Image.alpha_composite(parts[name],parts['Ink_'+name]);box=(150,730,750,1070) if s=='L' else (1290,730,1890,1070)
 for row,bgcolor in enumerate(['white','#344050']):
  tile=im.crop(box).resize((800,453));bg=Image.new('RGB',tile.size,bgcolor);bg.paste(tile,(0,0),tile);sheet.paste(bg,(col*800,row*500+30));d.text((col*800+12,row*500+8),s+' / cleaned tips',fill='black')
sheet.save(out/'qa/cleaned-tips-light-dark.jpg',quality=97)
psd=PSDImage.new('RGBA',(2048,2048),color=0)
for group_name,names in groups:
 group=Group.new(group_name,parent=psd)
 for n in names:
  im=parts[n];box=im.getbbox();layer=PixelLayer.frompil(im.crop(box),psd_file=psd,layer_name=n,top=box[1],left=box[0]);group.append(layer)
  if n.endswith('_Iris'):layer.clipping_layer=True
  im.save(out/'layers'/f'{n}.png')
psdpath=out/'Rurino_Front_SmallTails_v034.psd';psd.save(psdpath);del psd;gc.collect()
saved=PSDImage.open(psdpath);actual=saved.composite(force=True);actual.save(out/'qa/front-smalltails.png')
# This checks file integrity and unchanged layers; visual review remains needed.
unchanged=[]
for group in saved:
 for layer in group:
  n=layer.name;im=Image.new('RGBA',(2048,2048));im.paste(layer.topil().convert('RGBA'),layer.offset)
  assert np.array_equal(np.array(im),np.array(parts[n])),n
  if n not in ['SideHair_L','SideHair_R','Ink_SideHair_L','Ink_SideHair_R']:
   assert np.array_equal(np.array(im),np.array(oldparts[n])),n
   unchanged.append(n)
for s in 'LR':
 a=np.array(parts['SideHair_'+s]);num,labels,stats,_=cv2.connectedComponentsWithStats((a[:,:,3]>30).astype('uint8'),8)
 assert len([r for r in stats[1:] if r[-1]>8])==1,stats.tolist()
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
report={'stage':'small-tail artwork cleanup; static model','source_psd_sha256':sha(source/'Rurino_Front_SmallTails_v034.psd'),'psd_sha256':sha(psdpath),'layers':31,'repairs':records,'other_layers_pixel_exact':unchanged,'checks':['saved PSD layers exactly match PNGs','one main connected component per tail at alpha>30; no islands larger than8px'],'limitations':['does not certify all hair finished','inferred hidden artwork retained','no animation binding']}
(out/'qa/material-checks.json').write_text(json.dumps(report,indent=2)+'\n');(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
cmopath=out/'Rurino_Front_SmallTails_v034.cmo3'
if not cmopath.exists():shutil.copy2(source/cmopath.name,cmopath)
print(json.dumps(report,indent=2))
