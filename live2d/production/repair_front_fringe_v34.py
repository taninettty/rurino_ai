"""Repair frontal fringe gaps and contamination; static materials, no animation."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
from restore_front_neutral_v34 import path_alpha
from PIL import Image,ImageDraw
import numpy as np,cv2
root=Path(__file__).resolve().parents[1];base=root/'rebuild_v3_4';src=base/'front_smalltails_clean/layers';out=base/'front_fringe_clean'
for folder in ['colour','ink','layers','qa','qa-runtime','runtime','runtime-reexport']:(out/folder).mkdir(parents=True,exist_ok=True)
raw=np.array(Image.open(root/'reference_v34/rurino_head_master_v34.png').convert('RGBA'))
# Lower silhouettes follow the original source contours, not an eye-difference mask.
paths={
'L':'M 641 490 L 853 490 C 816 552 777 618 757 693 Q 746 741 752 778 C 720 750 696 724 683 699 C 670 750 666 780 666 818 C 669 865 683 914 695 948 L 681 935 L 680 973 C 657 902 636 831 628 762 C 620 688 622 597 641 490 Z',
'R':'M 1121 490 L 1373 490 C 1396 567 1408 658 1403 735 C 1400 810 1384 896 1365 949 L 1360 937 L 1337 948 C 1358 891 1372 853 1381 812 C 1369 783 1359 749 1353 706 C 1339 746 1321 777 1301 794 C 1313 750 1315 709 1312 672 C 1300 714 1278 749 1257 772 C 1255 714 1210 638 1163 530 C 1168 634 1168 742 1105 817 C 1144 734 1148 650 1136 564 Q 1130 523 1121 490 Z'}
for side in 'LR':
 a=np.array(Image.open(src/f'Bang_{side}.png'));old=a.copy();mask=path_alpha(paths[side],(0,0,2048,2048))
 # Blend the existing alpha into the accurately traced lower silhouette over
 # the join band; copy source only where old opacity was missing.
 w=np.clip((np.arange(2048)-500)/15,0,1)[:,None];a[:,:,3]=np.rint(old[:,:,3]*(1-w)+mask*w)
 yy,xx=np.indices(a.shape[:2])
 protected=((xx < 620+np.maximum(yy-600,0)*.15) if side=='L' else ((xx>1490-.14*yy)|((yy<620)&(xx<1150))))
 protected&=(yy<620)
 a[:,:,3][protected]=old[:,:,3][protected]
 missing=np.clip((a[:,:,3].astype(float)-old[:,:,3])/255,0,1)
 a[:,:,:3]=np.rint(old[:,:,:3]*(1-missing[:,:,None])+raw[:,:,:3]*missing[:,:,None])
 # Root slit is a segmentation gap, not an intentional see-through hair part.
 top=(old[:,:,3]>127).astype('uint8');top[500:]=0
 points=cv2.findNonZero(top);hull=cv2.convexHull(points);fill=np.zeros_like(top);cv2.fillConvexPoly(fill,hull,255)
 yy,xx=np.indices(fill.shape)
 if side=='L':fill[xx>1000-.6*yy]=0
 else:fill[xx<1030+.6*yy]=0
 miss=np.maximum(fill.astype(float)-a[:,:,3],0)/255
 a[:,:,:3]=np.rint(a[:,:,:3]*(1-miss[:,:,None])+raw[:,:,:3]*miss[:,:,None]);a[:,:,3]=np.maximum(a[:,:,3],fill)
 n,lab,stats,_=cv2.connectedComponentsWithStats((a[:,:,3]>20).astype('uint8'),8);main=1+np.argmax(stats[1:,-1]);keep=cv2.dilate((lab==main).astype('uint8'),np.ones((3,3),np.uint8));a[:,:,3]*=keep;a[a[:,:,3]==0]=0
 # Reconstruct only the narrow lower-edge band from nearby hair colour.
 # Exclude dark source ink and old skin cutouts from the sampling palette.
 yy=np.arange(2048)[:,None]
 dep=cv2.distanceTransform((a[:,:,3]>200).astype('uint8'),cv2.DIST_L2,5)
 valid=((old[:,:,3]>240)&(a[:,:,3]>240)&(dep>8)&(old[:,:,:3].min(2)>115)&(old[:,:,:3].mean(2)>165)).astype('uint8')
 _,labels=cv2.distanceTransformWithLabels(1-valid,cv2.DIST_L2,5,labelType=cv2.DIST_LABEL_PIXEL)
 palette=old[:,:,:3][valid>0];padded=palette[np.maximum(labels-1,0)]
 padded=cv2.GaussianBlur(padded,(9,9),0)
 area=(yy>510)&(a[:,:,3]>0)&((old[:,:,3]<245)|(dep<6))
 rgb=a[:,:,:3].astype('int16')
 area|=(yy>510)&(a[:,:,3]>0)&(dep<12)&(rgb[:,:,0]-rgb[:,:,2]>12)&(rgb[:,:,1]>180)
 blend=np.clip((yy-510)/45,0,1)*area
 a[:,:,:3]=np.rint(a[:,:,:3]*(1-blend[:,:,None])+padded*blend[:,:,None]).astype('uint8')
 a[a[:,:,3]==0]=0
 Image.fromarray(a).save(out/'colour'/f'Bang_{side}.png')
import json,hashlib,gc
from complete_front_smalltails_v34 import compose,contour
from psd_tools import PSDImage
from psd_tools.api.layers import Group,PixelLayer
source=base/'front_smalltails_clean';manifest=json.loads((source/'manifest.json').read_text());parts={r['name']:Image.open(source/r['file']).convert('RGBA') for r in manifest['layers']}
oldparts=parts.copy()
for side in 'LR':
 n='Bang_'+side;parts[n]=Image.open(out/'colour'/f'{n}.png').convert('RGBA');a=np.array(contour(parts[n]));a[:480,:,3]=0;a[480:530,:,3]=np.rint(a[480:530,:,3]*(np.arange(50)/50)[:,None]);a[a[:,:,3]==0]=0
 parts['Ink_'+n]=Image.fromarray(a);parts['Ink_'+n].save(out/'ink'/f'Ink_{n}.png')
# Place the temple locks above both fringe pieces so their overlap remains hidden.
manifest['groups'][-1][1]=['Bang_L','Ink_Bang_L','Bang_R','Ink_Bang_R','CheekLock_L','CheekLock_R','FrontLock_R_Long','Flower_L','Flower_R','Brow_L','Brow_R']
for side in 'LR':manifest['layers'].append({'name':'Ink_Bang_'+side,'file':'layers/Ink_Bang_'+side+'.png','clip_to':None})
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
unchanged=[n for n in oldparts if n not in ['Bang_L','Bang_R']]
assert all(np.array_equal(np.array(parts[n]),np.array(oldparts[n])) for n in unchanged)
for n,im in parts.items():im.save(out/'layers'/f'{n}.png')
# Same background for before/after; both light and dark backgrounds for final edges.
sheet=Image.new('RGB',(1600,1040),'#dce1e8');d=ImageDraw.Draw(sheet)
for col,side in enumerate('LR'):
 n='Bang_'+side;box=(600,80,1060,1000) if side=='L' else (1000,80,1430,1000)
 for row in range(2):
  im=oldparts[n] if row==0 else Image.alpha_composite(parts[n],parts['Ink_'+n]);im=im.crop(box);im.thumbnail((740,470));bg=Image.new('RGB',(780,480),'#344050');bg.paste(im,((780-im.width)//2,0),im);sheet.paste(bg,(col*800+10,row*520+32));d.text((col*800+15,row*520+10),side+(' / BEFORE' if row==0 else ' / REPAIRED'),fill='black')
sheet.save(out/'qa/fringe-before-after.jpg',quality=97)
sheet=Image.new('RGB',(1600,920),'#ddd');d=ImageDraw.Draw(sheet)
for col,side in enumerate('LR'):
 im=Image.alpha_composite(parts['Bang_'+side],parts['Ink_Bang_'+side]).crop((610,600,810,990) if side=='L' else (1090,600,1420,980));im.thumbnail((740,420))
 for row,color in enumerate(['white','#344050']):
  bg=Image.new('RGB',(780,430),color);bg.paste(im,((780-im.width)//2,0),im);sheet.paste(bg,(col*800+10,row*460+25));d.text((col*800+10,row*460+5),side+' / cleaned tips',fill='black')
sheet.save(out/'qa/fringe-tips-light-dark.jpg',quality=97)
compose(parts,manifest['groups']).save(out/'qa/front-fringe.png')
psd=PSDImage.new('RGBA',(2048,2048),color=0)
for groupname,names in manifest['groups']:
 group=Group.new(groupname,parent=psd)
 for n in names:
  im=parts[n];box=im.getbbox();layer=PixelLayer.frompil(im.crop(box),psd_file=psd,layer_name=n,top=box[1],left=box[0]);group.append(layer)
  if n.endswith('_Iris'):layer.clipping_layer=True
psdpath=out/'Rurino_Front_Fringe_v034.psd';psd.save(psdpath);del psd;gc.collect()
saved=PSDImage.open(psdpath)
for group in saved:
 for layer in group:
  full=Image.new('RGBA',(2048,2048));full.paste(layer.topil().convert('RGBA'),(layer.left,layer.top));assert np.array_equal(np.array(full),np.array(parts[layer.name])),layer.name
saved.composite(force=True).save(out/'qa/front-fringe.png')
report={'stage':'frontal fringe artwork repair; no animation','layers':len(parts),'unchanged_layers_pixel_exact':unchanged,'checks':['saved PSD matches all PNG layers','right forehead skin wedge removed','left inner cutout opened'],'psd_sha256':hashlib.sha256(psdpath.read_bytes()).hexdigest(),'source_psd_sha256':hashlib.sha256((source/'Rurino_Front_SmallTails_v034.psd').read_bytes()).hexdigest(),'limitations':['two frontal fringe groups retained, not every strand independently rigged','temple locks, large tails and support still need cleanup','27 default parameters unbound']}
assert np.array(parts['Bang_R'])[650,1200,3]==0
assert np.array(parts['Bang_L'])[750,700,3]==0
(out/'qa/material-checks.json').write_text(json.dumps(report,indent=2)+'\n')
print('Saved',psdpath,len(parts),'layers; unchanged',len(unchanged))
