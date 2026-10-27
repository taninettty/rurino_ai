"""Registered eye/neutral-mouth materials with independent iris clipping.
Not a blink rig, talking mouth, or X/Y head rig. Preserves prior checkpoints.
"""
import gc,json
from pathlib import Path
import cv2,numpy as np
from scipy.ndimage import binary_fill_holes,distance_transform_edt
from PIL import Image,ImageDraw,ImageFilter
from psd_tools import PSDImage
from psd_tools.api.layers import Group,PixelLayer
from split_head_v34 import OUT as BASE,thumbnail,mask
BROWS=BASE/'brow_refinement';OUT=BASE/'face_features';SIZE=(2048,2048)
OCCLUDERS={
 'CheekLock_L':'M 305 335 L 339 335 C 332 375 330 408 339 444 Q 345 465 350 480 L 305 480 Z',
 'Bang_L':'M 335 335 L 389 335 C 383 355 379 380 376 394 Q 353 368 335 335 Z',
 'Bang_R_A':'M 574 335 L 579 335 C 577 365 569 391 558 403 Q 570 379 574 335 Z',
 'Bang_R_B':'M 607 335 L 650 335 Q 647 364 632 388 Q 633 363 607 335 Z',
 'Bang_R_C':'M 650 335 L 677 335 Q 673 373 654 400 Q 660 366 650 335 Z',
 'CheekLock_R':'M 679 335 L 720 335 L 720 480 L 668 480 Q 681 450 685 418 Q 689 379 679 335 Z',
}

def occlusion_masks(mother,raw):
    result={}
    for name,path in OCCLUDERS.items():
        m=mask(path).astype('uint8');ys,xs=np.nonzero(m);x0=max(0,int(xs.min())-12);x1=min(2048,int(xs.max())+13);y0=int(ys.min())-12;y1=int(ys.max())+13
        sub=m[y0:y1,x0:x1];kernel=np.ones((7,7),np.uint8)
        g=np.where(sub>0,cv2.GC_PR_FGD,cv2.GC_PR_BGD).astype('uint8');g[cv2.erode(sub,kernel)>0]=cv2.GC_FGD;g[cv2.dilate(sub,kernel)==0]=cv2.GC_BGD
        cv2.grabCut(mother[y0:y1,x0:x1,:3].copy(),g,None,np.zeros((1,65)),np.zeros((1,65)),3,cv2.GC_INIT_WITH_MASK)
        m[y0:y1,x0:x1]=((g==cv2.GC_FGD)|(g==cv2.GC_PR_FGD)).astype('uint8')
        key='Bang_R' if name.startswith('Bang_R') else name
        result[key]=result.get(key,np.zeros(SIZE,np.uint8))|m
    # Extend traced seeds to the real pink/blond tips that cover the dark eye plate.
    # This separates hair colour from eye-edge registration noise and iris highlights.
    o=mother[:,:,:3].astype('int16');reference=raw[:,:,:3].astype('int16')
    delta=np.max(np.abs(o-reference),axis=2)
    candidate=(delta>45)&(o[:,:,0]>145)&(((o[:,:,0]-reference[:,:,0]>55)&(o[:,:,0]-o[:,:,1]>7))|((o[:,:,0]-o[:,:,1]>27)&(o[:,:,2]-o[:,:,1]>7)))
    roi=np.zeros(SIZE,bool);roi[700:940,650:950]=True;roi[700:940,1100:1400]=True;candidate &= roi
    candidate=cv2.morphologyEx(candidate.astype('uint8'),cv2.MORPH_OPEN,np.ones((5,5),np.uint8))
    candidate=cv2.morphologyEx(candidate,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    candidate=cv2.dilate(candidate,np.ones((3,3),np.uint8))>0
    keys=list(result);distances=np.stack([distance_transform_edt(m==0) for m in result.values()]);owner=np.argmin(distances,axis=0)
    candidate &= distances.min(axis=0)<32
    for i,n in enumerate(keys):result[n]|=(candidate&(owner==i)).astype('uint8')
    return result

def soften(m,r=.45):return np.array(Image.fromarray(m.astype('uint8')*255).filter(ImageFilter.GaussianBlur(r)))
def rgba(rgb,alpha):
    p=np.zeros((*alpha.shape,4),np.uint8);p[:,:,:3]=rgb[:,:,:3];p[:,:,3]=alpha;p[alpha==0]=0;return Image.fromarray(p)
def fit_iris(raw,white,opening,roi):
    x,y,r,b=roi
    rr=cv2.resize(raw,(1024,1024));ww=cv2.resize(white,(1024,1024));oo=cv2.resize(opening,(1024,1024))
    x0,y0,r0,b0=[v//2 for v in roi]
    diff=np.max(np.abs(rr[y0:b0,x0:r0,:3].astype('int16')-ww[y0:b0,x0:r0,:3].astype('int16')),2)
    seed=((diff>30)&(oo[y0:b0,x0:r0]>100)).astype('uint8')
    seed=cv2.morphologyEx(seed,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    cs,_=cv2.findContours(seed,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE);c=max(cs,key=cv2.contourArea);c=c[c[:,0,1]+y0>400]
    (cx,cy),(dx,dy),ang=cv2.fitEllipse(c)
    ellipse=(((cx+x0)*2,(cy+y0)*2),((dx+.8)*2,(dy+.8)*2),ang)
    full=np.zeros((2048,2048),np.uint8);cv2.ellipse(full,ellipse,255,-1,cv2.LINE_AA)
    # Remove captured white crescents while filling the intentional white specular highlights.
    dd=np.max(np.abs(raw[y:b,x:r,:3].astype('int16')-white[y:b,x:r,:3].astype('int16')),2)
    seed=((dd>25)&(opening[y:b,x:r]>100)&(full[y:b,x:r]>0)).astype('uint8')
    seed=cv2.morphologyEx(seed,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
    n,cc,stats,_=cv2.connectedComponentsWithStats(seed);main=cc==(1+np.argmax(stats[1:,4]))
    visible=binary_fill_holes(main)
    local=full[y:b,x:r].copy();local[(opening[y:b,x:r]>100)&~visible]=0
    full[y:b,x:r]=local
    return full,ellipse

def main():
    for d in ['layers','masks','qa']: (OUT/d).mkdir(exist_ok=True)
    man=json.loads((BROWS/'manifest.json').read_text());parts={x['name']:Image.open(BROWS/x['file']).convert('RGBA') for x in man['layers']}
    mother=np.array(Image.open(BROWS/'sources/master-browless-local.png'))
    raw=np.array(Image.open(BASE/'underpaint/skin-underpaint-raw.png'))
    blank=np.array(Image.open(OUT/'sources/featureless-skin.png'))
    white=np.array(Image.open(OUT/'sources/eye-white-source.png'))
    occluders=occlusion_masks(mother,raw);hair_mask=np.maximum.reduce(list(occluders.values()))>0
    for n,m in occluders.items():Image.fromarray(m*255).save(OUT/'masks'/f'{n}_EyeOcclusion.png')
    # Original visible eye pixels are retained; only formerly occluded parts use the bald reference.
    close=np.max(np.abs(mother[:,:,:3].astype('int16')-raw[:,:,:3].astype('int16')),2)<25
    # Generated underpainting shifts a few high-contrast texels without moving the eye.
    # Compare a tiny neighbourhood, otherwise old iris/lash outlines survive as ghosts.
    for x,y,r,b in [(640,690,960,950),(1090,690,1410,950),(910,1055,1130,1145)]:
        original=mother[y:b,x:r,:3].astype('int16');best=np.full(original.shape[:2],255,np.int16)
        for dy in range(-3,4):
            for dx in range(-3,4):
                candidate=raw[y+dy:b+dy,x+dx:r+dx,:3].astype('int16')
                best=np.minimum(best,np.max(np.abs(original-candidate),axis=2))
        close[y:b,x:r]=best<25
    target=raw.copy();target[close]=mother[close]
    target[hair_mask]=raw[hair_mask]
    for x,y,r,b in [(650,700,950,940),(1100,700,1400,940),(920,1065,1120,1135)]:
        exposed=~hair_mask[y:b,x:r];target[y:b,x:r][exposed]=mother[y:b,x:r][exposed]
    features={};openings={};iris_masks={};ellipses={};feature_mask=np.zeros(SIZE,np.uint8)
    rois={'L':(650,700,950,940),'R':(1100,700,1400,940)}
    yy=np.arange(2048)[:,None]
    for side,roi in rois.items():
        x,y,r,b=roi;w=white[y:b,x:r,:3].astype('int16')
        seed=(w.min(2)>135)&(np.ptp(w,axis=2)<24)
        n,cc,stats,_=cv2.connectedComponentsWithStats(seed.astype('uint8'));seed=(cc==(1+np.argmax(stats[1:,4]))).astype('uint8')
        seed=cv2.morphologyEx(seed,cv2.MORPH_CLOSE,np.ones((3,3),np.uint8))
        ap=np.zeros(SIZE,np.uint8);ap[y:b,x:r]=soften(seed,.45);openings[side]=ap
        iris,ellipse=fit_iris(raw,white,ap,roi);iris_masks[side]=iris;ellipses[side]=ellipse
        # Keep original sclera outside the hidden iris footprint; fill its centre from LibTV.
        features['Eye_'+side+'_White']=rgba(white,ap)
        features['Eye_'+side+'_Iris']=rgba(target,iris)
        difference=np.max(np.abs(raw[y:b,x:r,:3].astype('int16')-blank[y:b,x:r,:3].astype('int16')),2)
        dark=raw[y:b,x:r,:3].min(2)<205
        # Exclude hair/ear contours at the far sides of the rectangular review ROI.
        outline=(difference>16)&dark
        # Keep components attached to eye lashes/crease, not the nearby ear boundary.
        n,cc,stats,centers=cv2.connectedComponentsWithStats(outline.astype('uint8'))
        valid=np.zeros_like(outline)
        for j in range(1,n):
            sx,sy,sw,sh,area=stats[j];cx,cy=centers[j]
            if area>16 and sy+sh<228 and (sx+sw>40 and sx<265):valid|=cc==j
        fm=np.zeros(SIZE,np.uint8);fm[y:b,x:r]=soften(valid,.3)
        fm=np.maximum(fm,ap)
        feature_mask=np.maximum(feature_mask,fm)
        lid=np.maximum(fm.astype('int16')-ap.astype('int16'),0).astype('uint8')
        for name,condition in [('UpperLid',yy<884),('LowerLid',yy>=884)]:
            alpha=lid*condition
            f=alpha.astype('float32')[...,None]/255
            unmatte=np.clip(np.rint((target[:,:,:3]-blank[:,:,:3]*(1-f))/np.maximum(f,1/255)),0,255).astype('uint8')
            features['Eye_'+side+'_'+name]=rgba(unmatte,alpha)
        for name,m in [('Opening',ap),('Iris',iris),('Feature',fm)]:Image.fromarray(m).save(OUT/'masks'/f'Eye_{side}_{name}.png')
    # Neutral frontal mouth only: no stretch-to-open approximation.
    x,y,r,b=(920,1065,1120,1135)
    difference=np.max(np.abs(raw[y:b,x:r,:3].astype('int16')-blank[y:b,x:r,:3].astype('int16')),2)
    mouth=np.zeros(SIZE,np.uint8);mouth[y:b,x:r]=soften((difference>12)&(raw[y:b,x:r,:3].min(2)<235),.45)
    features['Mouth_Neutral']=rgba(target,mouth);feature_mask=np.maximum(feature_mask,mouth)
    Image.fromarray(mouth).save(OUT/'masks/Mouth_Neutral.png')
    # Complete skin underneath the features. No old eyes remain on skin/support/hair.
    patch=cv2.dilate((feature_mask>0).astype('uint8'),np.ones((9,9),np.uint8))
    visible_remove=(patch>0)&~hair_mask
    face=np.array(parts['Face_Reference']);source_alpha=mother[:,:,3]
    face[visible_remove,:3]=blank[visible_remove,:3];face[visible_remove,3]=source_alpha[visible_remove]
    parts['Face_Reference']=Image.fromarray(face)
    for n,im in list(parts.items()):
        if n in ['Face_Reference','BackHair_Concealed_Support','Brow_L','Brow_R']:continue
        a=np.array(im)
        if n=='Skin_Concealed_Support':
            a[patch>0,:3]=blank[patch>0,:3]
        else:a[visible_remove]=0
        a[a[:,:,3]==0]=0;parts[n]=Image.fromarray(a)
    # Original partition assigned a few occluding bang pixels to Face_Reference.
    # Restore their actual foreground ownership before placing complete eyelids behind hair.
    for foreground,occluder in occluders.items():
        occ=(patch>0)&(occluder>0)&(mother[:,:,3]>250)
        fg=np.array(parts[foreground]);fg[occ]=mother[occ];parts[foreground]=Image.fromarray(fg)
        for n in [name for name in parts if name not in [foreground,'BackHair_Concealed_Support','Skin_Concealed_Support','Brow_L','Brow_R']]:
            p=np.array(parts[n]);p[occ]=0;parts[n]=Image.fromarray(p)
    base_names=['BackHair_Concealed_Support','Skin_Concealed_Support','Ponytail_L','Ponytail_R','Body_Reference','Neck_Reference','Face_Reference','Ear_L','Ear_R']
    front_names=[n for n in parts if n not in base_names and not n.startswith('Brow_')]
    def render(gaze=(0,0),show_eyes=True,show_mouth=True):
        result=Image.new('RGBA',SIZE)
        for n in base_names:result.alpha_composite(parts[n])
        if show_eyes:
            for side in ['L','R']:
                moving=Image.new('RGBA',SIZE);moving.alpha_composite(features['Eye_'+side+'_Iris'],gaze)
                arr=np.array(moving);eye=np.array(features['Eye_'+side+'_White']);f=arr[:,:,3].astype('float32')[...,None]/255
                eye[:,:,:3]=np.rint(arr[:,:,:3]*f+eye[:,:,:3]*(1-f)).astype('uint8')
                result.alpha_composite(Image.fromarray(eye))
                result.alpha_composite(features['Eye_'+side+'_UpperLid']);result.alpha_composite(features['Eye_'+side+'_LowerLid'])
        if show_mouth:result.alpha_composite(features['Mouth_Neutral'])
        for n in front_names:result.alpha_composite(parts[n])
        result.alpha_composite(parts['Brow_L']);result.alpha_composite(parts['Brow_R'])
        return result
    neutral=render();neutral.save(OUT/'qa/neutral.png');render(show_eyes=False,show_mouth=False).save(OUT/'qa/features-hidden.png')
    allparts={**parts,**features}
    for n,im in allparts.items():im.save(OUT/'layers'/f'{n}.png')
    psd=PSDImage.new('RGBA',SIZE,color=0)
    def group(name,items):
        g=Group.new(name,parent=psd)
        for n in items:
            im=allparts[n];box=im.getbbox()
            if not box:continue
            l=PixelLayer.frompil(im.crop(box),psd_file=psd,layer_name=n,top=box[1],left=box[0]);g.append(l)
            if n.endswith('_Iris'):l.clipping_layer=True
    group('01_Body_and_Skin',base_names)
    for side in ['L','R']:group('02_Eye_'+side,['Eye_'+side+'_'+n for n in ['White','Iris','UpperLid','LowerLid']])
    group('03_Neutral_Mouth',['Mouth_Neutral']);group('04_Foreground_Hair',front_names);group('05_Brows',['Brow_L','Brow_R'])
    path=OUT/'Rurino_Head_Facial_Materials_v034.psd';psd.save(path);del psd;gc.collect()
    reopened=PSDImage.open(path);check=np.array(reopened.composite(force=True));del reopened;gc.collect()
    expected=np.array(neutral);diff=np.abs(check.astype('int16')-expected.astype('int16'))
    # Photoshop clipping is retained; Cubism must explicitly set iris -> eye white clipping IDs.
    old=np.array(Image.open(BROWS/'qa/neutral.png'));delta=np.abs(expected.astype('int16')-old.astype('int16'))
    qa=Image.new('RGB',(1400,760),(225,229,237));d=ImageDraw.Draw(qa)
    for i,(label,im) in enumerate([('Before eye separation',Image.fromarray(old)),('Independent eyes + original neutral mouth',neutral)]):
        tile=thumbnail(im.crop((440,260,1600,1400)),(700,700),(225,229,237));qa.paste(tile,(700*i,40));d.text((700*i+12,15),label,fill=(40,45,55))
    qa.save(OUT/'qa/neutral-before-after.jpg',quality=95)
    sheet=Image.new('RGB',(1000,750),(42,47,60));d=ImageDraw.Draw(sheet)
    for j,(name,im) in enumerate(features.items()):
        box=im.getbbox();tile=thumbnail(im.crop(box),(310,190),(42,47,60));x=(j%3)*333;y=(j//3)*250;sheet.paste(tile,(x,y+35));d.text((x+12,y+10),name,fill='white')
    sheet.save(OUT/'qa/facial-layer-sheet.jpg',quality=94)
    gazes=[(-12,0),(0,0),(12,0),(0,-8),(0,8)]
    grid=Image.new('RGB',(480*len(gazes),540),(225,229,237));d=ImageDraw.Draw(grid);tests=[]
    for i,gaze in enumerate(gazes):
        im=render(gaze);tile=thumbnail(im.crop((460,600,1580,1160)),(480,480),(225,229,237));grid.paste(tile,(i*480,35));d.text((i*480+12,10),'Iris shift '+str(gaze),fill=(40,40,50))
        # Irises cannot draw outside the fixed aperture after explicit clipping.
        tests.append({'gaze_full_resolution_px':gaze,'clipping':'iris alpha multiplied by fixed eye-white alpha'})
    grid.save(OUT/'qa/gaze-tests.jpg',quality=94)
    frames=[]
    for k in range(36):
        gaze=(round(12*np.sin(k*2*np.pi/36)),round(5*np.sin(k*4*np.pi/36)))
        im=render(gaze);tile=thumbnail(im.crop((380,180,1660,1400)),(640,640),(225,229,237));ImageDraw.Draw(tile).text((12,10),'IRIS CLIPPING CHECK / MATERIALS ONLY',fill=(40,45,60));frames.append(tile)
    frames[0].save(OUT/'qa/gaze-material-check.gif',save_all=True,append_images=frames[1:],duration=90,loop=0,disposal=2)
    thumbnail(neutral,(800,800),(225,229,237)).save(OUT/'qa/head-progress.jpg',quality=95)
    report={'status':'facial material checkpoint; not rigged','layer_count':len(allparts),'iris_ellipses_in_2048':ellipses,'neutral_vs_previous_mean_rgb':float(delta[:,:,:3].mean()),'psd_alpha_error_max':int(diff[:,:,3].max()),'psd_rgb_error_max':int(diff[:,:,:3][expected[:,:,3]>0].max()),'gaze_tests':tests,'remaining':['inspect edge matting and neutral eye likeness before Cubism import','eye closure requires eyelid/white keyforms and masking, not whole-eye scaling','neutral mouth only, no open mouth cavity or lip-sync forms','head X/Y perspective and full-body integration remain pending','shared rear support still needs separate tail-root ownership']}
    (OUT/'qa/checks.json').write_text(json.dumps(report,indent=2));(OUT/'manifest.json').write_text(json.dumps({'canvas':SIZE,'layers':[{'name':n,'file':'layers/'+n+'.png','clip_to':n.replace('_Iris','_White') if n.endswith('_Iris') else None} for n in allparts]},indent=2))
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
