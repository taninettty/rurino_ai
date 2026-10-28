"""Trace visible left-view components without warping; preserve existing eye keyforms.

This is a first ownership split. Hidden plates are optional reference supports;
not complete per-part roots or a Cubism model. Coordinates below are at 1024.
"""
import gc,hashlib,json
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
from psd_tools import PSDImage
from psd_tools.api.layers import Group,PixelLayer
from split_head_v34 import mask
ROOT=Path(__file__).resolve().parents[1];TURN=ROOT/'rebuild_v3_4/turn_redraw';OUT=TURN/'left_head_parts';SOURCE=TURN/'side_blink_refinement/left/Rurino_Turn_Left_Blink_Materials_v034.psd'
FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
PATHS={
'Body_Visible':'M 444 645 Q 409 651 371 678 Q 307 709 237 722 L 236 738 Q 202 733 182 777 Q 146 835 110 1024 L 916 1024 Q 874 841 840 790 Q 815 753 787 739 L 789 723 Q 718 708 649 673 Q 609 652 577 644 Z',
'ShortRearHair_ImageLeft':'M 274 104 Q 236 116 212 170 Q 191 222 184 274 Q 164 343 103 385 Q 125 395 164 366 Q 152 421 158 450 Q 163 474 183 487 L 177 453 Q 190 486 216 505 L 207 468 Q 228 501 255 505 L 284 362 L 333 158 Z',
'ShortRearHair_ImageRight':'M 706 99 Q 762 89 802 145 Q 836 204 853 276 Q 882 349 950 382 Q 919 391 876 366 Q 892 421 876 455 Q 866 480 851 494 L 855 449 Q 840 493 808 508 Q 827 474 825 454 Q 802 500 756 518 Q 778 469 771 430 Q 755 362 730 271 Z',
'CrownBangs_Visible':'M 497 57 Q 445 36 379 72 Q 293 114 263 196 Q 234 283 225 372 Q 204 452 236 514 Q 253 559 289 596 Q 321 622 367 645 Q 335 605 322 551 L 332 449 L 595 438 L 573 559 L 551 636 Q 600 607 640 553 Q 685 500 705 449 Q 723 411 715 363 L 733 294 Q 745 190 704 122 Q 669 72 608 59 Q 550 42 497 57 Z',
'Neck_Visible':'M 445 576 L 579 548 Q 570 611 578 651 Q 583 678 614 692 L 589 774 L 512 750 L 437 775 L 414 691 Q 441 680 448 648 Z',
'FacePaint_Visible_NOT_FEATURE_SPLIT':'M 436 171 Q 427 185 420 180 L 403 175 Q 369 221 342 282 Q 324 325 316 363 L 322 387 Q 307 375 302 366 Q 290 405 300 447 Q 312 490 337 538 Q 363 569 405 601 Q 425 620 435 620 Q 505 596 548 570 Q 581 548 602 519 Q 630 480 637 438 Q 621 404 598 377 Q 590 389 573 396 Q 590 375 593 350 L 581 376 L 568 381 Q 582 345 580 322 Q 567 362 551 376 Q 547 348 525 309 L 497 264 Q 502 331 488 364 L 475 390 Q 486 344 481 304 Q 473 251 458 215 Q 447 188 436 171 Z',
'Ear_Near_ImageRight':'M 691 399 Q 704 396 716 414 Q 730 438 718 457 Q 699 486 665 510 L 648 525 Q 660 495 668 468 Q 682 432 691 399 Z',
'CheekLock_ImageLeft':'M 374 95 Q 330 137 310 192 Q 288 251 276 310 Q 264 366 278 419 Q 295 462 328 491 Q 311 464 304 442 Q 311 500 336 545 Q 310 527 298 510 Q 308 562 330 596 Q 345 625 367 645 Q 310 615 278 573 Q 249 538 230 493 Q 215 457 217 417 Q 226 330 251 253 Q 281 165 327 125 Z',
'CheekLock_ImageRight':'M 551 77 Q 610 104 648 153 Q 686 201 697 259 Q 712 332 697 403 Q 687 460 662 506 Q 633 560 591 604 L 551 636 Q 574 601 592 548 Q 603 515 604 485 Q 587 511 559 530 Q 585 499 601 461 Q 623 404 633 345 Q 642 288 628 230 Q 611 149 551 77 Z',
'LongFrontLock_ImageRight':'M 696 359 Q 725 401 742 453 Q 756 498 747 532 Q 758 621 760 704 Q 758 766 773 820 Q 790 865 788 900 Q 787 950 824 988 Q 841 1008 835 1024 L 799 1024 Q 811 1010 799 996 Q 768 970 754 934 Q 744 899 752 862 Q 753 832 746 802 Q 732 734 733 674 Q 730 597 723 534 Q 729 503 714 461 Q 700 415 689 386 Z',
'Flower_ImageLeft':'M 288 104 Q 287 77 306 63 Q 320 52 331 80 Q 337 46 351 47 Q 364 48 360 78 Q 372 57 379 66 Q 388 85 370 107 Q 361 135 341 159 Q 312 207 278 232 Q 254 250 237 250 Q 228 246 241 232 Q 218 244 216 230 Q 214 214 239 198 Q 218 194 227 181 Q 234 167 259 166 Q 242 154 251 143 Q 231 117 251 107 Q 270 99 288 104 Z',
'Flower_ImageRight':'M 650 79 Q 647 64 660 68 Q 660 48 676 48 Q 690 49 694 80 Q 714 49 730 60 Q 750 70 728 103 Q 754 93 772 110 Q 783 128 766 144 Q 789 151 781 167 Q 801 162 808 180 Q 809 197 790 199 Q 816 216 809 231 Q 805 243 783 233 Q 799 249 781 252 Q 755 250 730 232 Q 703 215 689 186 Q 666 158 657 128 Q 645 103 650 79 Z'
}
# Visible flower boundary follows the actual diagonal bang occlusion.
PATHS['Flower_ImageLeft']='M 288 104 Q 287 77 306 63 Q 320 52 331 80 Q 337 46 351 47 Q 364 48 360 78 Q 372 57 379 66 Q 381 79 376 89 Q 339 109 304 143 Q 270 180 251 218 L 237 250 Q 228 246 241 232 Q 218 244 216 230 Q 214 214 239 198 Q 218 194 227 181 Q 234 167 259 166 Q 242 154 251 143 Q 231 117 251 107 Q 270 99 288 104 Z'
# The long thin strand starts behind the short blue lock, not at the ear.
PATHS['LongFrontLock_ImageRight']='M 689 497 L 735 492 Q 734 548 741 601 Q 749 672 752 700 Q 760 765 770 802 Q 776 840 780 873 Q 787 917 811 952 Q 833 982 839 1000 Q 843 1015 826 1024 L 780 1024 Q 820 1007 811 993 Q 797 972 776 950 Q 749 920 746 901 Q 741 884 747 870 Q 765 836 762 811 Q 744 764 731 711 Q 716 662 703 606 Q 690 552 689 497 Z'
PATHS['TempleLock_ImageRight']='M 598 79 Q 679 116 707 199 Q 725 251 726 300 Q 750 377 752 429 Q 750 486 720 525 Q 739 477 735 435 Q 727 387 711 351 Q 695 294 680 244 Q 664 175 628 131 Z'
DIVIDER='M 0 0 L 497 0 L 497 57 Q 470 83 436 171 L 436 1024 L 0 1024 Z'
def pixels(g):
 for l in g:
  if l.is_group():yield from pixels(l)
  else:yield l

def dump(p,r):p.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def add(psd,g,im,name,offset=(0,0)):
 box=im.getbbox();assert box,name
 l=PixelLayer.frompil(im.crop(box),psd_file=psd,layer_name=name,top=box[1]+offset[1],left=box[0]+offset[0]);g.append(l);return l

def clone(src,parent,psd,records):
 for item in src:
  if item.is_group():
   g=Group.new(item.name,parent=parent);g.visible=item.visible;g.opacity=item.opacity
   if item.blend_mode is not None:g.blend_mode=item.blend_mode
   clone(item,g,psd,records)
  else:
   im=item.topil().convert('RGBA');l=PixelLayer.frompil(im,psd_file=psd,layer_name=item.name,top=item.top,left=item.left);parent.append(l);l.visible=item.visible;l.opacity=item.opacity;l.clipping_layer=item.clipping_layer
   if item.blend_mode is not None:l.blend_mode=item.blend_mode
   records.append({'name':item.name,'offset':list(item.offset),'size':list(im.size),'rgba_sha256':hashlib.sha256(im.tobytes()).hexdigest(),'clipping':bool(item.clipping_layer)})
def main():
 for n in ['layers','masks','qa']:(OUT/n).mkdir(exist_ok=True)
 src=PSDImage.open(SOURCE);context=next(l for l in pixels(src) if l.name=='Context_Skin_Reference');a=np.array(context.topil().convert('RGBA'));assert a.shape==(2048,2048,4)
 # Every visible source pixel has one owner, including antialias. No nearest
 # anatomy fill: the first two broad regions are the existing rear/tail context.
 names=['RearTail_ImageLeft_Visible','RearTail_ImageRight_Visible'];owner=np.where(np.indices((2048,2048))[1]<1024,0,1).astype('uint8')
 # Prime the upper silhouette as rear hair, then trace foreground shapes.
 # This retains roots outside the original crown outline without assigning
 # upper hair/flower scraps to the lower ponytails.
 for name in PATHS:names.append(name)
 yy,xx=np.indices(owner.shape);crown=names.index('CrownBangs_Visible')
 owner[(yy<1000)&(xx<1024)]=names.index('ShortRearHair_ImageLeft')
 owner[(yy<1000)&(xx>=1024)]=names.index('ShortRearHair_ImageRight')
 for name,path in PATHS.items():owner[mask(path)]=names.index(name)
 owner[(owner==crown)&(yy>800)&(xx<900)]=names.index('CheekLock_ImageLeft')
 owner[(owner==crown)&(yy>800)&(xx>=900)]=names.index('CheekLock_ImageRight')
 crown=names.index('CrownBangs_Visible');names[crown]='Bang_ImageLeft_Visible';names.append('Bang_ImageRight_Visible');owner[(owner==crown)&~mask(DIVIDER)]=len(names)-1
 # Inspect disconnected islands rather than silently deleting them. Keep
 # every original RGBA pixel in a clearly named review layer; do not pretend
 # uncertain boundaries are finished independently movable hair parts.
 review_id=len(names);names.append('Boundary_Review_NOT_RIG_READY');transfers=[]
 for i,name in enumerate(names[:-1]):
  visible=((owner==i)&(a[:,:,3]>0)).astype('uint8')
  count,labels,stats,centroids=cv2.connectedComponentsWithStats(visible,8)
  if count<=2:continue
  main_id=1+int(np.argmax(stats[1:,cv2.CC_STAT_AREA]))
  for component in range(1,count):
   if component==main_id:continue
   # Clothing/ponytails are legitimately disconnected by foreground locks.
   if name in ['Body_Visible','RearTail_ImageLeft_Visible','RearTail_ImageRight_Visible'] and stats[component,cv2.CC_STAT_AREA]>10000:continue
   hit=labels==component;area=int(stats[component,cv2.CC_STAT_AREA]);owner[hit]=review_id
   transfers.append({'source':name,'pixels':area,'bbox':stats[component,:4].tolist(),'target':names[review_id]})
 parts={};manifest=[];recon=np.zeros_like(a)
 for i,name in enumerate(names):
  m=owner==i;p=a.copy();p[~m]=0
  if not np.any(p[:,:,3]):continue
  im=Image.fromarray(p);parts[name]=im;im.save(OUT/'layers'/f'{name}.png');Image.fromarray((m*255).astype('uint8')).save(OUT/'masks'/f'{name}.png');recon[m]=p[m]
  manifest.append({'name':name,'bbox':list(im.getbbox()),'visible_pixels':int((p[:,:,3]>0).sum()),'file':'layers/'+name+'.png','status':'visible ownership only; concealed anatomy not complete'})
 assert np.array_equal(recon,a)
 # Flat guide is review-only, not a part mask for Cubism.
 colors=[(236,115,140),(80,159,218),(122,115,183),(86,188,176),(231,166,73),(236,190,140),(200,141,198),(160,199,89),(231,124,65),(126,176,216),(176,138,87),(205,101,150),(121,135,217),(122,202,178),(230,202,119)]
 rgb=np.array([colors[i%len(colors)] for i in range(len(names))],np.uint8)[owner];overlay=Image.fromarray(np.dstack([rgb,np.where(a[:,:,3]>0,190,0).astype('uint8')]))
 bg=Image.new('RGBA',(2048,2048),(234,238,245,255));bg.alpha_composite(Image.fromarray(a));bg.alpha_composite(overlay);bg.resize((1000,1000)).convert('RGB').save(OUT/'qa/visible-ownership-map.jpg',quality=96)
 sheet=Image.new('RGB',(1600,380*((len(parts)+3)//4)),(234,238,245));d=ImageDraw.Draw(sheet);font=ImageFont.truetype(FONT,15)
 for i,(name,im) in enumerate(parts.items()):
  tile=im.crop(im.getbbox());tile.thumbnail((390,335));x=(i%4)*400;y=(i//4)*380;sheet.paste(tile,(x+(400-tile.width)//2,y+35),tile);d.text((x+6,y+8),name,font=font,fill='#253149')
 sheet.save(OUT/'qa/left-head-visible-layer-sheet.jpg',quality=96)
 psd=PSDImage.new('RGBA',(2048,2048),color=0);g=Group.new('01_Left_Visible_Head_Parts_ROOTS_PENDING',parent=psd)
 for name,im in parts.items():add(psd,g,im,name)
 copied=[]
 for item in src:
  if item.name.startswith('01_Context'):continue
  clone([item],psd,psd,copied)
 path=OUT/'Rurino_Left_Head_Visible_Parts_v034.psd';psd.save(path)
 dump(OUT/'traced-paths.json',{'coordinates':'1024 drawing coordinates, multiply by 2 for native pixels','paths':PATHS,'bang_divider':DIVIDER})
 dump(OUT/'manifest.json',{'canvas':[2048,2048],'source_psd':str(SOURCE.relative_to(ROOT)),'source_sha256':sha(SOURCE),'context_rgba_sha256':hashlib.sha256(a.tobytes()).hexdigest(),'parts':manifest,'preserved_eye_and_overlap_layers':copied,'part_count':len(parts),'pixel_layer_count':len(parts)+len(copied),'partition_exact':True,'disconnected_islands_retained_for_review':transfers,'psd_sha256':sha(path),'scope':'first left-view visible component split; not all hidden roots or facial subparts are complete','limits':['nose mouth and brows not independently separated in this stage','far ear is occluded and has not been invented','local foreground eye-hair overlap still belongs to existing blink reference group','visible part ownership requires visual boundary review','no Cubism mesh binding or continuous rotation verification']})
 print(json.dumps({'parts':len(parts),'preserved_layers':len(copied),'psd':str(path),'partition_exact':True},indent=2))
if __name__=='__main__':main()
