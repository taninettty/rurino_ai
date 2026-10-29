"""Complete frontal small-tail hidden roots from registered back-hair underpaint.
Existing visible hair colours are retained. Hidden geometry is a traced inference,
not an assertion that the unseen original artwork has been recovered.
"""
import gc,hashlib,json
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw
from psd_tools import PSDImage
from psd_tools.api.layers import Group,PixelLayer
from restore_front_neutral_v34 import path_alpha
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'rebuild_v3_4/front_neutral'
OUT=ROOT/'rebuild_v3_4/front_smalltails'
# Coordinates on the 2048 canvas; curves follow the inner strand flow.
# These masks only supply the missing interior; original exposed edges survive.
FILL={
'L':'M 516 206 C 565 192 611 235 624 288 C 637 355 617 464 630 572 C 640 684 675 759 730 798 Q 684 795 650 760 Q 678 833 736 873 Q 670 868 607 834 Q 633 865 663 880 Q 603 887 550 839 Q 561 896 590 921 Q 523 917 463 875 Q 498 976 539 1038 Q 476 1013 424 966 C 369 893 363 781 380 666 C 399 545 419 445 446 348 Q 474 226 516 206 Z',
'R':'M 1530 204 C 1480 194 1430 238 1418 290 C 1407 358 1425 468 1411 573 C 1397 687 1364 759 1304 799 Q 1353 795 1387 761 Q 1359 835 1300 874 Q 1366 869 1430 835 Q 1403 865 1375 880 Q 1434 887 1487 838 Q 1475 895 1446 920 Q 1513 918 1574 874 Q 1537 976 1498 1041 Q 1561 1014 1613 967 C 1669 894 1671 781 1655 666 C 1635 545 1617 444 1590 346 Q 1560 225 1530 204 Z',
}
NAMES=['SideHair_L','SideHair_R']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def compose(parts,groups):
 out=Image.new('RGBA',(2048,2048))
 for _,names in groups:
  for n in names:
   if n.endswith('_Iris'):continue
   im=parts[n]
   if n.endswith('_White') and n.replace('_White','_Iris') in parts:
    # PSD clipping composes the clipped RGB before applying base-layer alpha.
    white=np.array(im);alpha=white[:,:,3].copy();white[:,:,3]=255
    im=Image.alpha_composite(Image.fromarray(white),parts[n.replace('_White','_Iris')]);a=np.array(im);a[:,:,3]=alpha;im=Image.fromarray(a)
   out.alpha_composite(im)
 return out

def contour(im):
 a=np.array(im);alpha=a[:,:,3]
 # Antialiased inward border, 1.5 source pixels: do not widen the silhouette.
 scale=3;hi=np.array(Image.fromarray(alpha).resize((6144,6144),Image.Resampling.LANCZOS))
 inside=(hi>127).astype('uint8');depth=cv2.distanceTransform(np.pad(inside,1),cv2.DIST_L2,5)[1:-1,1:-1]/scale
 cov=np.clip((1.65-depth)/.6,0,1)*inside
 line=np.array(Image.fromarray((cov*170).astype('uint8')).resize((2048,2048),Image.Resampling.LANCZOS))
 line=np.minimum(line,alpha);ink=np.zeros_like(a);ink[:,:,3]=line
 return Image.fromarray(ink)

def main():
 for f in ['layers','colour','ink','masks','qa']:(OUT/f).mkdir(parents=True,exist_ok=True)
 manifest=json.loads((SOURCE/'manifest.json').read_text());groups=manifest['groups'];parts={r['name']:Image.open(SOURCE/r['file']).convert('RGBA') for r in manifest['layers']}
 old={k:v.copy() for k,v in parts.items()};raw=np.array(Image.open(ROOT/'rebuild_v3_4/underpaint/backhair-underpaint-raw.png').convert('RGBA'))
 records=[]
 for side in ['L','R']:
  n='SideHair_'+side;a=np.array(parts[n]);mask=path_alpha(FILL[side],(0,0,2048,2048))
  # Close tiny enclosed root gaps left between the independently traced
  # existing silhouette and the hidden fill, never outside the combined outline.
  union=(np.maximum(mask,a[:,:,3])>127).astype('uint8');flood=union.copy();cv2.floodFill(flood,None,(0,0),2)
  mask[flood==0]=255
  fill=raw.copy();fill[:,:,3]=np.minimum(mask,raw[:,:,3]);fill[fill[:,:,3]==0]=0
  # Blend the inferred hidden material beneath original source texels.
  distance=cv2.distanceTransform((a[:,:,3]>127).astype('uint8'),cv2.DIST_L2,5)
  weight=np.clip(distance/24,0,1)
  blend=(fill[:,:,3]>250)&(a[:,:,3]>0)
  softened=a.copy()
  softened[:,:,:3][blend]=np.rint(a[:,:,:3][blend]*weight[blend,None]+raw[:,:,:3][blend]*(1-weight[blend,None])).astype('uint8')
  merged=Image.alpha_composite(Image.fromarray(fill),Image.fromarray(softened));parts[n]=merged
  ink=contour(merged);parts['Ink_'+n]=ink
  for _,names in groups:
   if n in names:names.insert(names.index(n)+1,'Ink_'+n)
  merged.save(OUT/'colour'/f'{n}.png');ink.save(OUT/'ink'/f'Ink_{n}.png');Image.fromarray(mask).save(OUT/'masks'/f'{n}_HiddenCompletion.png')
  records.append({'part':n,'added_alpha_pixels':int(((np.array(merged)[:,:,3]>127)&(a[:,:,3]<128)).sum()),'original_opaque_rgb_preserved_outside_24px_join':bool(np.array_equal(np.array(merged)[:,:,:3][(a[:,:,3]==255)&(distance>=24)],a[:,:,:3][(a[:,:,3]==255)&(distance>=24)]))})
 # Small tails are behind the face; completed hidden strands must never cover eyes.
 for _,names in groups:
  names[:]=[n for n in names if n not in ['SideHair_L','Ink_SideHair_L','SideHair_R','Ink_SideHair_R']]
 body=groups[0][1];position=body.index('Body_Reference')
 body[position:position]=['SideHair_L','Ink_SideHair_L','SideHair_R','Ink_SideHair_R']
 before= Image.open(SOURCE/'qa/front-neutral.png').convert('RGBA')
 after=compose(parts,groups);before.save(OUT/'qa/before.png');after.save(OUT/'qa/front-smalltails.png')
 # Show isolated material, rather than hiding root problems under flowers.
 sheet=Image.new('RGB',(1600,1000),'#dce2eb');d=ImageDraw.Draw(sheet)
 for col,side in enumerate(['L','R']):
  n='SideHair_'+side;new=Image.alpha_composite(parts[n],parts['Ink_'+n]);box=(140,130,800,1090) if side=='L' else (1230,130,1900,1090)
  for row,im in enumerate([old[n],new]):
   tile=im.crop(box);tile.thumbnail((720,450));x=col*800+40;y=row*500+42
   bg=Image.new('RGB',(720,450),'#384759');bg.paste(tile,((720-tile.width)//2,0),tile);sheet.paste(bg,(x,y));d.text((x,y-25),side+(' BEFORE' if row==0 else ' COMPLETED / separate contour'),fill='#243244')
 sheet.save(OUT/'qa/smalltails-before-after.jpg',quality=96)
 sheet=Image.new('RGB',(1400,740),'#e3e8f0');d=ImageDraw.Draw(sheet)
 for i,im in enumerate([before,after]):
  tile=im.resize((700,700));sheet.paste(tile,(i*700,40),tile);d.text((i*700+12,12),['Before','Completed small-tail roots + contours'][i],fill='#243244')
 sheet.save(OUT/'qa/assembly-before-after.jpg',quality=96)
 psd=PSDImage.new('RGBA',(2048,2048),color=0)
 for group_name,names in groups:
  group=Group.new(group_name,parent=psd)
  for n in names:
   im=parts[n];box=im.getbbox();layer=PixelLayer.frompil(im.crop(box),psd_file=psd,layer_name=n,top=box[1],left=box[0]);group.append(layer)
   if n.endswith('_Iris'):layer.clipping_layer=True
   im.save(OUT/'layers'/f'{n}.png')
 path=OUT/'Rurino_Front_SmallTails_v034.psd';psd.save(path);del psd;gc.collect()
 saved=PSDImage.open(path);actual=saved.composite(force=True);actual.save(OUT/'qa/front-smalltails.png');a=np.array(actual);e=np.array(after);err=np.abs(a.astype('int16')-e.astype('int16'));premul=np.abs(a[:,:,:3].astype(float)*a[:,:,3,None]/255-e[:,:,:3].astype(float)*e[:,:,3,None]/255);assert premul.max()<=5,(premul.max(),int(err[:,:,3].max()));assert err[:,:,3].max()<=2
 # PSD clipping and PIL integer compositing differ at eye antialias pixels;
 # independently protect the visible eyes against the prior canonical PSD.
 for x,y,r,b in [(710,770,920,910),(1104,768,1335,910)]:
  assert np.abs(a[y:b,x:r].astype('int16')-np.array(before)[y:b,x:r].astype('int16')).max()<=2
 # All source materials except the two completed hair sheets are byte-identical.
 check=[]
 for group in saved:
  for layer in group:
   n=layer.name
   if n in old and n not in NAMES:
    im=Image.new('RGBA',(2048,2048));im.paste(layer.topil().convert('RGBA'),layer.offset)
    assert np.array_equal(np.array(im),np.array(old[n])),n
    check.append(n)
 rep={'stage':'frontal small-tail material completion; no new animation binding','source_psd_sha256':sha(SOURCE/'Rurino_Front_Neutral_v034.psd'),'psd_sha256':sha(path),'layers':len(parts),'repairs':records,'other_layers_pixel_exact':check,'saved_psd_premultiplied_max_difference':float(premul.max()),'saved_psd_alpha_max_difference':int(err[:,:,3].max()),'new_ink_layers':['Ink_SideHair_L','Ink_SideHair_R'],'limitations':['hidden fill inferred from prior generated registered back-hair plate','fringe and large tails not completed in this pass','not an animation or motion-range acceptance test']}
 (OUT/'qa/material-checks.json').write_text(json.dumps(rep,indent=2)+'\n');(OUT/'manifest.json').write_text(json.dumps({'canvas':[2048,2048],'groups':groups,'layers':[{'name':n,'file':f'layers/{n}.png','clip_to':n.replace('_Iris','_White') if n.endswith('_Iris') else None} for n in parts]},indent=2)+'\n');print(json.dumps(rep,indent=2))
if __name__=='__main__':main()
