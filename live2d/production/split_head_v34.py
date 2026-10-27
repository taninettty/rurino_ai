"""v3.4 carefully traced visible-source layers, NOT an animation-ready rig.
Coordinates use 1024-square reference; L/R are viewer sides.
Visible ownership is a disjoint partition to detect loss/duplication exactly.
Hidden underpainting is a separate operation and cannot be inferred from this QA.
"""
import json,re,hashlib
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer,Group
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'rebuild_v3_4'
W=H=2048
PATHS={
'Ponytail_L':'M 255 115 Q 217 245 219 469 C 184 628 102 744 0 878 L 0 1024 L 150 1024 L 393 656 L 397 385 Z',
'Ponytail_R':'M 762 112 Q 809 251 811 468 C 844 632 926 764 1024 871 L 1024 1024 L 871 1024 L 625 653 L 629 384 Z',
'Body_Reference':'M 444 644 Q 413 655 386 669 Q 313 704 241 727 L 236 744 Q 202 742 183 777 C 145 841 120 942 110 1024 L 845 1024 Q 832 864 814 791 Q 801 751 782 744 L 784 730 Q 709 711 636 671 Q 606 652 576 643 Z',
'Neck_Reference':'M 438 579 L 584 578 Q 574 625 583 663 Q 590 685 610 695 L 586 773 L 510 754 L 438 777 L 414 693 Q 437 683 443 650 Z',
'SideHair_L':'M 260 101 Q 225 95 206 139 Q 185 191 174 250 Q 153 335 88 388 Q 117 395 158 366 Q 141 419 153 454 Q 161 476 174 490 L 172 454 Q 186 495 216 510 L 204 479 Q 232 516 274 522 Q 236 487 247 423 L 304 186 L 336 123 Z',
'SideHair_R':'M 762 102 Q 798 99 817 143 Q 838 203 850 260 Q 876 340 938 389 Q 906 390 869 367 Q 881 431 869 458 Q 861 478 847 491 L 849 456 Q 834 498 802 510 L 813 480 Q 785 514 750 525 Q 780 486 772 420 L 716 179 L 690 123 Z',
'Hair_CrownFront':'M 504 59 Q 467 42 411 63 Q 309 88 270 188 C 245 249 250 284 235 371 Q 219 425 231 471 Q 245 490 260 506 C 283 576 337 625 399 658 Q 369 625 356 572 L 337 484 Q 344 497 356 508 L 369 467 L 665 468 L 677 504 L 647 575 Q 639 608 622 650 Q 681 614 715 551 Q 745 508 758 455 Q 775 388 752 298 Q 749 227 708 169 Q 659 93 576 62 Q 530 48 504 59 Z',
'Face_Reference':'M 521 139 Q 505 159 507 176 L 483 169 Q 466 191 435 242 L 394 318 L 374 372 Q 359 400 340 425 Q 339 470 356 511 Q 370 553 395 576 Q 430 602 482 629 Q 507 642 518 634 Q 570 610 619 576 Q 642 553 662 511 Q 678 469 685 427 Q 664 404 645 371 L 603 293 Q 576 259 569 231 Q 548 163 521 139 Z',
'Ear_L':'M 340 468 Q 336 488 347 510 Q 351 522 362 521 L 369 515 L 359 490 Z',
'Ear_R':'M 680 469 Q 688 487 675 509 Q 668 522 658 521 L 652 515 L 664 489 Z',
# Cheek locks follow the longitudinal stroke, never a horizontal bang cut.
'CheekLock_L':'M 345 213 C 324 253 312 302 313 352 C 308 395 313 438 331 489 Q 349 540 380 572 Q 354 526 343 485 Q 350 553 365 593 Q 376 631 399 658 C 350 628 310 594 284 547 Q 260 504 251 461 Q 244 420 255 374 Q 259 310 288 262 Q 312 225 345 213 Z',
'CheekLock_R':'M 685 219 C 708 269 711 319 706 362 Q 708 418 688 473 Q 672 524 649 553 Q 669 519 677 484 Q 666 562 645 607 L 623 650 Q 670 616 697 578 Q 730 532 746 478 Q 762 420 752 365 Q 747 297 718 250 Z',
'FrontLock_R_Long':'M 735 454 Q 744 517 751 598 Q 759 691 766 773 Q 772 815 769 854 Q 760 899 789 944 Q 825 974 836 994 Q 840 1006 831 1024 L 799 1024 Q 813 1007 801 994 Q 765 976 750 936 Q 738 903 747 860 Q 750 826 747 793 Q 740 702 733 638 Q 724 552 728 491 Z',
'Flower_L':'M 286 103 Q 276 79 291 65 Q 310 49 323 78 Q 323 51 340 49 Q 354 49 354 76 Q 363 63 367 76 Q 369 96 353 118 Q 340 155 322 181 Q 308 218 275 239 Q 249 256 235 250 Q 229 246 243 234 Q 215 244 213 230 Q 208 215 235 195 Q 216 192 222 180 Q 230 161 259 163 Q 248 150 255 145 Q 239 117 261 105 Q 273 100 286 103 Z',
'Flower_R':'M 650 80 Q 650 65 660 69 Q 661 49 674 49 Q 689 49 692 77 Q 705 49 720 62 Q 739 75 723 105 Q 745 94 760 112 Q 776 130 760 144 Q 778 151 773 165 Q 792 161 800 180 Q 802 194 782 197 Q 807 213 800 229 Q 797 240 779 234 Q 793 249 780 251 Q 755 254 727 234 Q 701 217 691 186 Q 673 155 661 127 Q 649 105 650 80 Z',
}
# Trace the actual fringe edge rather than a triangle enclosing hair and skin.
PATHS['Face_Reference']='M 521 139 Q 510 151 507 176 L 483 169 Q 448 211 414 269 Q 379 323 363 386 L 350 376 L 341 380 L 344 389 L 336 389 L 341 398 L 333 400 L 339 411 Q 335 432 344 450 Q 346 478 356 510 Q 371 551 395 576 Q 432 604 482 629 Q 507 642 518 634 Q 571 610 619 576 Q 643 553 662 511 Q 676 475 680 445 Q 689 425 682 410 L 686 397 L 677 392 L 680 381 L 671 384 L 663 376 L 656 381 Q 670 343 672 327 Q 674 369 660 392 L 650 383 Q 648 372 650 363 L 645 374 L 634 368 Q 608 358 581 379 Q 567 389 559 401 C 580 331 572 251 549 194 Q 536 160 521 139 Z'
PATHS['CheekLock_L']='M 432 85 C 369 121 335 184 320 261 C 306 328 310 405 334 473 Q 350 527 380 572 Q 351 551 337 523 Q 349 604 399 658 C 342 625 301 579 275 532 Q 249 484 247 437 Q 246 377 267 319 Q 284 258 309 201 Q 344 137 396 105 Z'
PATHS['CheekLock_R']='M 603 85 Q 665 123 700 177 Q 739 239 751 307 Q 765 388 751 451 Q 740 512 705 566 Q 674 613 622 650 Q 650 602 667 540 Q 654 550 647 555 Q 674 514 686 465 C 708 390 707 321 690 257 Q 665 157 603 85 Z'

def mask(path):
    tokens=re.findall(r'[MLCQZ]|-?\d+(?:\.\d+)?',path);i=0;p=np.zeros(2);points=[]
    while i<len(tokens):
        op=tokens[i];i+=1;n={'M':2,'L':2,'Q':4,'C':6,'Z':0}[op]
        vals=np.array([float(v) for v in tokens[i:i+n]]).reshape(-1,2);i+=n
        if op in ('M','L'):p=vals[0];points.append(p)
        elif op in ('Q','C'):
            for t in np.linspace(0,1,80)[1:]:
                points.append((1-t)**2*p+2*(1-t)*t*vals[0]+t*t*vals[1] if op=='Q' else (1-t)**3*p+3*(1-t)**2*t*vals[0]+3*(1-t)*t*t*vals[1]+t**3*vals[2])
            p=vals[-1]
    m=Image.new('L',(W,H));ImageDraw.Draw(m).polygon([(round(x*2),round(y*2)) for x,y in points],fill=255)
    return np.array(m)>0

def clean_source(source):
    a=np.array(source);alpha=a[:,:,3]
    # Disconnected generation debris only; preserve fine connected strands.
    n,labels,stats,_=cv2.connectedComponentsWithStats((alpha>24).astype('uint8'))
    ids=[i for i in range(1,n) if stats[i,cv2.CC_STAT_AREA]>500]
    keep=cv2.dilate(np.isin(labels,ids).astype('uint8'),np.ones((3,3),np.uint8))
    alpha=alpha*keep
    # Remove near-white matte contamination only when connected to transparency.
    white=(a[:,:,:3].min(axis=2)>237)&(np.ptp(a[:,:,:3],axis=2)<18)
    outside=(alpha<8).astype('uint8')
    for _ in range(24):
        grow=cv2.dilate(outside,np.ones((3,3),np.uint8))
        updated=outside|((grow>0)&white).astype('uint8')
        if np.array_equal(updated,outside):break
        outside=updated
    alpha[outside>0]=0
    a[:,:,3]=alpha;a[alpha==0]=0
    return a

def thumbnail(a,size=(340,340),bg=(44,49,62)):
    im=Image.fromarray(a) if isinstance(a,np.ndarray) else a
    im=im.copy();im.thumbnail(size)
    b=Image.new('RGB',size,bg);b.paste(im,((size[0]-im.width)//2,(size[1]-im.height)//2),im if im.mode=='RGBA' else None);return b

def main():
    for d in ['layers','masks','qa']: (OUT/d).mkdir(parents=True,exist_ok=True)
    src=ROOT/'reference_v34/rurino_head_master_v34.png';original=Image.open(src).convert('RGBA');a=clean_source(original)
    Image.fromarray(a).save(OUT/'master-cleaned.png')
    ownership=np.zeros((H,W),np.uint8);names=['Unassigned_Review']
    for name,path in PATHS.items():
        names.append(name);ownership[mask(path)]=len(names)-1
    # Crown's left/right main bangs separate at their actual center part.
    crown_id=names.index('Hair_CrownFront');crown=ownership==crown_id
    divider=mask('M 0 0 L 504 0 L 505 88 Q 517 113 521 139 Q 508 159 507 176 L 507 1024 L 0 1024 Z')
    names[crown_id]='Bang_L';names.append('Bang_R');ownership[crown&~divider]=len(names)-1
    # Tiny boundary omissions go to the nearest traced region; keep the mask as evidence.
    missing=(ownership==0)&(a[:,:,3]>0)
    Image.fromarray((missing*255).astype('uint8')).save(OUT/'qa/initial-unassigned-mask.png')
    if np.any(missing):
        from scipy.ndimage import distance_transform_edt
        _,nearest=distance_transform_edt(ownership==0,return_indices=True)
        ownership[missing]=ownership[tuple(nearest[:,missing])]
    # Visible detached cheek strokes must not remain assigned to a bang controller.
    # Transfer whole connected strokes, never crop them with a horizontal cut.
    for side in ['L','R']:
        bid=names.index('Bang_'+side)
        n,cc,stats,centers=cv2.connectedComponentsWithStats(((ownership==bid)&(a[:,:,3]>24)).astype('uint8'))
        main=1+int(np.argmax(stats[1:,cv2.CC_STAT_AREA]))
        for j in range(1,n):
            if j==main:continue
            x,y=centers[j]/2
            if y<220:continue
            target='CheekLock_'+side if ((x<350) if side=='L' else (x>675)) else 'Face_Reference'
            ownership[cc==j]=names.index(target)
    layers=[];recon=np.zeros_like(a);counts=[]
    psd=PSDImage.new('RGBA',(W,H),color=0);group=Group.new('VISIBLE_ONLY__hidden_roots_not_ready',parent=psd)
    sheet=Image.new('RGB',(340*4,380*((len(names)+3)//4)),(25,28,36));draw=ImageDraw.Draw(sheet)
    manifest=[]
    for idx,name in enumerate(names):
        m=ownership==idx;p=a.copy();p[~m]=0
        if not np.any(p[:,:,3]):continue
        im=Image.fromarray(p);im.save(OUT/'layers'/f'{name}.png');Image.fromarray((m*255).astype('uint8')).save(OUT/'masks'/f'{name}.png')
        recon[m]=p[m];box=im.getbbox();pixelcount=int(np.count_nonzero(p[:,:,3]));counts.append(pixelcount)
        layer=PixelLayer.frompil(im.crop(box),psd_file=psd,layer_name=name,top=box[1],left=box[0]);group.append(layer)
        index=len(manifest);x=(index%4)*340;y=(index//4)*380
        sheet.paste(thumbnail(im),(x,y+30));draw.text((x+10,y+8),name,fill='white')
        manifest.append({'name':name,'file':f'layers/{name}.png','bbox':box,'visible_pixels':pixelcount,'status':'visible-source-cut; hidden roots pending','parent_deformer':None,'artmesh_id':None})
    psd.save(OUT/'Rurino_Head_Visible_Cuts_v034.psd')
    sheet.save(OUT/'qa/layer-sheet.jpg',quality=92)
    Image.fromarray(recon).save(OUT/'qa/neutral-recomposition.png')
    # Verify the PSD as saved, not only the input buffers.
    reread=PSDImage.open(OUT/'Rurino_Head_Visible_Cuts_v034.psd');render=np.array(reread.composite(force=True))
    if render.shape[2]==3:raise AssertionError('PSD lost alpha')
    diff=np.abs(render.astype('int16')-a.astype('int16'));valid=a[:,:,3]>0
    checks={'scope':'visible-layer ownership and neutral export only; does not validate animation', 'source_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'layer_count':len(manifest),'partition_exact':bool(np.array_equal(a,recon)),'psd_alpha_max_error':int(diff[:,:,3].max()),'psd_visible_rgb_max_error':int(diff[:,:,:3][valid].max()),'remaining_unassigned_visible_pixels':int(np.count_nonzero((ownership==0)&valid)),'removed_alpha_pixels':int(np.count_nonzero((np.array(original)[:,:,3]>0)&(a[:,:,3]==0))),'animation_ready':False}
    (OUT/'manifest.json').write_text(json.dumps({'canvas':[W,H],'coordinate_system':'viewer left/right','layers':manifest,'validation':checks},ensure_ascii=False,indent=2))
    (OUT/'traced-paths.json').write_text(json.dumps(PATHS,indent=2))
    (OUT/'qa/checks.json').write_text(json.dumps(checks,indent=2))
    assert checks['partition_exact'] and checks['remaining_unassigned_visible_pixels']==0
    assert checks['psd_alpha_max_error']<=1, checks
    assert checks['psd_visible_rgb_max_error']<=2, checks
    light=thumbnail(Image.fromarray(a),(700,700),(226,229,237));dark=thumbnail(Image.fromarray(a),(700,700),(40,45,57))
    preview=Image.new('RGB',(1400,700));preview.paste(light);preview.paste(dark,(700,0));preview.save(OUT/'qa/light-dark-alpha.jpg',quality=95)
    print(json.dumps(checks,indent=2))
if __name__=='__main__':main()
