"""Separate original eyebrows from hair; only paste registered LibTV local repairs.
Retains step-one sources. Produces a material PSD, not a Cubism runtime.
"""
import json,hashlib
from pathlib import Path
import cv2,numpy as np
from scipy.ndimage import distance_transform_edt,median_filter
from PIL import Image,ImageDraw,ImageFilter
from psd_tools import PSDImage
from psd_tools.api.layers import Group,PixelLayer
from split_head_v34 import OUT as BASE,mask,thumbnail
OUT=BASE/'brow_refinement'
PATHS={
 'Brow_L':'M 333 351 C 358 331 389 318 411 320 C 433 320 454 327 467 339 C 447 326 420 325 397 329 C 372 332 350 341 333 351 Z',
 'Brow_R':'M 551 340 C 569 323 590 318 610 318 C 640 317 669 331 689 348 C 665 333 638 326 611 326 C 585 325 564 330 551 340 Z',
}

def save_psd(groups,path):
    psd=PSDImage.new('RGBA',(2048,2048),color=0)
    for name,parts in groups:
        g=Group.new(name,parent=psd)
        for n,im in parts.items():
            box=im.getbbox();g.append(PixelLayer.frompil(im.crop(box),psd_file=psd,layer_name=n,top=box[1],left=box[0]))
    psd.save(path)
    return PSDImage.open(path)

def main():
    for d in ['layers','masks','qa']: (OUT/d).mkdir(exist_ok=True)
    a=np.array(Image.open(BASE/'master-cleaned.png').convert('RGBA'))
    gen=np.array(Image.open(OUT/'sources/browless-source.png').convert('RGBA'))
    masks={};repair_mask=np.zeros(a.shape[:2],np.uint8)
    for name,path in PATHS.items():
        region=mask(path).astype('uint8')
        # A narrow local colour-difference refinement captures the actual dark outline.
        band=cv2.dilate(region,np.ones((7,7),np.uint8))>0
        core=cv2.erode(region,np.ones((3,3),np.uint8))>0
        difference=np.max(np.abs(a[:,:,:3].astype('int16')-gen[:,:,:3].astype('int16')),axis=2)
        selected=core|(band&(difference>18))
        selected=cv2.morphologyEx(selected.astype('uint8'),cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
        # Crossed hair contours can attach little vertical stubs to colour-difference
        # selections. Fit the continuous upper/lower brow silhouette before matting.
        ys,xs=np.nonzero(selected);x0,x1=int(xs.min()),int(xs.max())
        xx=np.arange(x0,x1+1)
        top=np.array([np.flatnonzero(selected[:,x])[0] for x in xx],dtype=float)
        bottom=np.array([np.flatnonzero(selected[:,x])[-1]+1 for x in xx],dtype=float)
        def smooth_contour(values):
            values=median_filter(values,size=9,mode='nearest')
            t=np.linspace(-1,1,len(values));keep=np.ones(len(t),bool)
            for _ in range(5):
                fit=np.polynomial.Polynomial.fit(t[keep],values[keep],4)
                residual=np.abs(values-fit(t));scale=np.median(residual[keep])
                keep=residual<max(1.0,3*scale)
            return fit(t)
        top=smooth_contour(top);bottom=smooth_contour(bottom)
        bottom=np.maximum(bottom,top+.2)
        y0=int(np.floor(top.min()))-3;y1=int(np.ceil(bottom.max()))+3
        shape=Image.new('L',((x1-x0+3)*4,(y1-y0)*4))
        points=[((x-x0+1)*4,(y-y0)*4) for x,y in zip(xx+.5,top)]
        points += [((x-x0+1)*4,(y-y0)*4) for x,y in zip((xx+.5)[::-1],bottom[::-1])]
        ImageDraw.Draw(shape).polygon(points,fill=255)
        small=shape.resize((x1-x0+3,y1-y0),Image.Resampling.LANCZOS)
        full=Image.new('L',(2048,2048));full.paste(small,(x0-1,y0));m=np.array(full)
        masks[name]=m;Image.fromarray(m).save(OUT/'masks'/f'{name}.png')
        repair_mask=np.maximum(repair_mask,cv2.dilate((m>0).astype('uint8'),np.ones((9,9),np.uint8)))
    # Feather only the outside of the repair. All eyebrow strokes are fully removed below.
    distance=cv2.distanceTransform(repair_mask,cv2.DIST_L2,5)
    weight=np.minimum(distance/4,1)[...,None]
    repaired=a.copy();repaired[:,:,:3]=np.rint(a[:,:,:3]*(1-weight)+gen[:,:,:3]*weight).astype('uint8')
    Image.fromarray(repaired).save(OUT/'sources/master-browless-local.png')
    Image.fromarray((repair_mask*255).astype('uint8')).save(OUT/'masks/local-repair-region.png')
    man=json.loads((BASE/'manifest.json').read_text());names=[x['name'] for x in man['layers']]
    ownership=np.zeros(a.shape[:2],np.uint8)
    for i,n in enumerate(names):
        p=np.array(Image.open(BASE/'layers'/f'{n}.png'))
        ownership[p[:,:,3]>0]=i+1
    # Fill ownership across the removed brow from the adjoining skin/hair regions.
    _,nearest=distance_transform_edt(repair_mask>0,return_indices=True)
    active=repair_mask>0;ownership[active]=ownership[tuple(nearest[:,active])]
    parts={}
    for i,n in enumerate(names):
        p=repaired.copy();p[ownership!=i+1]=0;parts[n]=Image.fromarray(p)
    supports={}
    for n in ['BackHair_Concealed_Support','Skin_Concealed_Support']:
        p=np.array(Image.open(BASE/'underpaint'/f'{n}.png'))
        if n.startswith('Skin'):
            # This plate has no hair lines: local skin-only inpainting removes duplicate brows.
            p[:,:,:3]=cv2.inpaint(p[:,:,:3],repair_mask*255,9,cv2.INPAINT_TELEA)
            p[p[:,:,3]==0]=0
        supports[n]=Image.fromarray(p)
    brows={}
    for n,m in masks.items():
        alpha=m.astype('float32')/255
        # Remove the old skin/hair matte from antialiased pixels of the independent brow.
        fg=(a[:,:,:3].astype('float32')-gen[:,:,:3]*(1-alpha[...,None]))/np.maximum(alpha[...,None],1/255)
        p=np.zeros_like(a);p[:,:,:3]=np.clip(np.rint(fg),0,255).astype('uint8');p[:,:,3]=m;p[m==0]=0
        brows[n]=Image.fromarray(p)
    allparts={**supports,**parts,**brows}
    for n,im in allparts.items():im.save(OUT/'layers'/f'{n}.png')
    def render(shifts=None,show_brows=True):
        result=Image.new('RGBA',(2048,2048))
        for n,im in allparts.items():
            if not show_brows and n in brows:continue
            result.alpha_composite(im,(shifts or {}).get(n,(0,0)))
        return result
    neutral=render();neutral.save(OUT/'qa/neutral.png')
    no_brows=render(show_brows=False);no_brows.save(OUT/'qa/brows-hidden.png')
    psd=save_psd([('01_Concealed_Plates',supports),('02_Browless_Visible_Parts',parts),('03_Independent_Brows',brows)],OUT/'Rurino_Head_Independent_Brows_v034.psd')
    rd=np.array(psd.composite(force=True));nd=np.array(neutral);err=np.abs(rd.astype('int16')-nd.astype('int16'))
    assert err[:,:,3].max()<=1 and err[:,:,:3][nd[:,:,3]>0].max()<=2
    assert np.array_equal(repaired[repair_mask==0],a[repair_mask==0])
    old=np.array(Image.open(BASE/'qa/head-with-concealed-plates.png'))
    diff=np.abs(nd.astype('int16')-old.astype('int16'))
    # Show isolated brows on dark and pale grounds to reveal attached hair/skin fragments.
    isolated=Image.new('RGBA',(2048,2048))
    for im in brows.values():isolated.alpha_composite(im)
    source_crop=(610,610,1430,725)
    sheet=Image.new('RGB',(1230,220*4),(40,45,57));d=ImageDraw.Draw(sheet)
    panels=[('Before: brows embedded in hair',Image.fromarray(old)),('Browless base: hair restored',no_brows),('Independent brows on dark background',isolated),('Neutral recomposition',neutral)]
    for i,(label,im) in enumerate(panels):
        crop=im.crop(source_crop).resize((1230,173));sheet.paste(crop,(0,i*220+35),crop);d.text((12,i*220+10),label,fill='white')
    sheet.save(OUT/'qa/brow-repair-detail.jpg',quality=95)
    cases={'neutral':{},'hair_left':{'Bang_L':(-12,0),'Bang_R':(-12,0),'CheekLock_L':(-12,0),'CheekLock_R':(-12,0)},'hair_right':{'Bang_L':(12,0),'Bang_R':(12,0),'CheekLock_L':(12,0),'CheekLock_R':(12,0)},'brows_up':{'Brow_L':(0,-10),'Brow_R':(0,-10)},'brows_down':{'Brow_L':(0,8),'Brow_R':(0,8)}}
    checks=[];grid=Image.new('RGB',(450*len(cases),530),(225,229,237));gd=ImageDraw.Draw(grid)
    opaque_brows=np.maximum(*masks.values())==255
    for i,(name,shifts) in enumerate(cases.items()):
        im=render(shifts);arr=np.array(im)
        drift=int(np.abs(arr[opaque_brows].astype('int16')-nd[opaque_brows].astype('int16')).max()) if name.startswith('hair') else None
        if drift is not None:assert drift==0
        checks.append({'case':name,'shifts_full_resolution':shifts,'opaque_brow_pixel_difference':drift})
        tile=thumbnail(im.crop((450,280,1590,1360)),(450,490),(225,229,237));grid.paste(tile,(450*i,35));gd.text((450*i+12,10),name,fill=(40,40,50))
    grid.save(OUT/'qa/independent-brow-tests.jpg',quality=94)
    frames=[]
    for k in range(40):
        t=np.sin(k/40*np.pi*2);dx=round(12*t)
        shifts={'Bang_L':(dx,0),'Bang_R':(dx,0),'CheekLock_L':(dx,0),'CheekLock_R':(dx,0)} if k<20 else {'Brow_L':(0,round(10*t)),'Brow_R':(0,round(10*t))}
        im=render(shifts);tile=thumbnail(im.crop((420,240,1620,1380)),(620,620),(225,229,237));ImageDraw.Draw(tile).text((12,12),'HAIR MOVES / BROWS STAY' if k<20 else 'BROWS MOVE / HAIR STAYS',fill=(35,40,55));frames.append(tile)
    frames[0].save(OUT/'qa/independent-brow-check.gif',save_all=True,append_images=frames[1:],duration=90,loop=0,disposal=2)
    thumbnail(neutral,(800,800),(225,229,237)).save(OUT/'qa/head-progress.jpg',quality=95)
    report={'status':'20-layer material source; no Cubism binding','layer_count':len(allparts),'outside_local_repair_pixels_unchanged':True,'neutral_change_outside_brow_repair_max':int(diff[repair_mask==0].max()),'neutral_change_inside_brow_repair_mean':float(diff[repair_mask>0].mean()),'neutral_change_inside_brow_repair_max':int(diff[repair_mask>0].max()),'psd_alpha_error_max':int(err[:,:,3].max()),'psd_rgb_error_max':int(err[:,:,:3][nd[:,:,3]>0].max()),'checks':checks,'limits':['eyelashes/eye whites/irises are not yet separately rigged','local hair seams outside the eyebrow region still require cleanup','layer shift checks are not head perspective or Cubism physics tests']}
    (OUT/'qa/checks.json').write_text(json.dumps(report,indent=2));(OUT/'brow-paths.json').write_text(json.dumps(PATHS,indent=2))
    (OUT/'manifest.json').write_text(json.dumps({'canvas':[2048,2048],'layers':[{'name':n,'file':'layers/'+n+'.png','bbox':im.getbbox()} for n,im in allparts.items()]},indent=2))
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
