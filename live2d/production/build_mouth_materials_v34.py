"""Frontal mouth materials from a registered LibTV plate; not a lip-sync rig."""
import gc
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw
from psd_tools import PSDImage
from psd_tools.api.layers import Group, PixelLayer
from scipy.ndimage import binary_fill_holes, gaussian_filter1d

from build_blink_materials_v34 import remap_rgba
from split_head_v34 import thumbnail

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'rebuild_v3_4/face_features'
BLINK=ROOT/'rebuild_v3_4/blink_refinement'
OUT=ROOT/'rebuild_v3_4/mouth_refinement'
BOX=(880,1040,1160,1195)
SIZE=(2048,2048)


def largest(mask):
    n,labels,stats,_=cv2.connectedComponentsWithStats(mask.astype('uint8'))
    assert n>1
    return labels==(1+np.argmax(stats[1:,4]))


def soften(mask):
    return cv2.GaussianBlur(mask.astype('float32'),(0,0),.45)


def rgba(rgb,alpha):
    a=np.zeros((*alpha.shape,4),np.uint8);a[:,:,:3]=np.clip(np.rint(rgb),0,255)
    a[:,:,3]=np.clip(np.rint(alpha*255),0,255);a[a[:,:,3]==0]=0
    return a


def bounds(mask):
    ys,xs=np.nonzero(mask);return int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())


def profiles(mask):
    columns=[];upper=[];lower=[]
    for x in range(mask.shape[1]):
        y=np.flatnonzero(mask[:,x])
        if len(y):columns.append(x);upper.append(y[0]);lower.append(y[-1])
    xx=np.arange(mask.shape[1])
    return tuple(gaussian_filter1d(np.interp(xx,columns,v),1) for v in [upper,lower])


def extract():
    source=np.array(Image.open(OUT/'sources/open-mouth-source.png').convert('RGBA').crop(BOX))
    blank=np.array(Image.open(SRC/'sources/featureless-skin.png').convert('RGBA').crop(BOX))
    neutral=np.array(Image.open(SRC/'layers/Mouth_Neutral.png').convert('RGBA').crop(BOX))
    r,g,b=source[:,:,:3].astype('int16').transpose(2,0,1)
    core=largest((r-g>35)&(g<180));l,t,right,bottom=bounds(core)
    closed_line=(neutral[:,:,3]>100)&(neutral[:,:,0]<180)&(neutral[:,:,1]<140)
    nl,_,nr,_=bounds(closed_line)
    def corner(mask,x):return float(np.nonzero(mask[:,x:x+3])[0].mean())
    left_y=corner(core,l);right_y=corner(core,right-2)
    target_y=(corner(closed_line,nl)+corner(closed_line,nr-2))/2
    sx=(nr-nl)/(right-l);sy=min(1.,55/(bottom-t))
    tilt=(right_y-left_y)/(right-l)
    matrix=np.array([[sx,0,nl-sx*l],[-sy*tilt,sy,target_y-sy*left_y+sy*tilt*l]],np.float32)
    registered=cv2.warpAffine(source,matrix,(source.shape[1],source.shape[0]),flags=cv2.INTER_CUBIC,borderMode=cv2.BORDER_REFLECT)
    Image.fromarray(registered).save(OUT/'qa/registered-mouth-crop.png')
    rgb=registered[:,:,:3].astype('float32');r,g,b=rgb.transpose(2,0,1)
    core=largest((r-g>35)&(g<180));filled=binary_fill_holes(core)
    aperture=soften(cv2.erode(filled.astype('uint8'),np.ones((3,3),np.uint8)))
    top,low=profiles(aperture>.5)
    difference=np.max(np.abs(rgb-blank[:,:,:3]),axis=2)
    near=cv2.dilate(filled.astype('uint8'),np.ones((15,15),np.uint8))>0
    feature=soften((difference>12)&near)
    feature=np.maximum(feature,aperture)
    lip_alpha=np.maximum(feature-aperture,0)
    yy=np.arange(source.shape[0])[:,None]
    teeth=largest((rgb.min(2)>190)&(np.ptp(rgb,axis=2)<40)&(aperture>.5))
    tongue=largest((r>175)&(g>100)&(g<185)&(r-g>40)&(aperture>.5))
    teeth_alpha=soften(teeth);tongue_alpha=soften(tongue)
    paint=cv2.dilate((teeth|tongue).astype('uint8'),np.ones((5,5),np.uint8))*255
    cavity=cv2.inpaint(registered[:,:,:3].copy(),paint,5,cv2.INPAINT_TELEA).astype('float32')
    parts={'Cavity':rgba(cavity,aperture)}
    for name,alpha in [('Teeth',teeth_alpha),('Tongue',tongue_alpha)]:
        color=(rgb-cavity*(1-alpha[:,:,None]))/np.maximum(alpha[:,:,None],1/255)
        parts[name]=rgba(color,alpha)
    lip_rgb=(rgb-blank[:,:,:3]*(1-lip_alpha[:,:,None]))/np.maximum(lip_alpha[:,:,None],1/255)
    parts['UpperLip']=rgba(lip_rgb,lip_alpha*(yy<(top+low)/2))
    parts['LowerLip']=rgba(lip_rgb,lip_alpha*(yy>=(top+low)/2))
    closed_top,closed_low=profiles(closed_line)
    line=(closed_top+closed_low)/2
    report={'source_bbox_global':[l+BOX[0],t+BOX[1],right+BOX[0],bottom+BOX[1]],
            'target_corner_x_global':[nl+BOX[0],nr+BOX[0]],
            'target_corner_y_global':target_y+BOX[1],
            'x_scale':sx,'y_scale':sy,'removed_corner_tilt_dy':right_y-left_y,
            'full_aperture_bbox_local':list(bounds(aperture>.5)),
            'teeth_pixels':int(teeth.sum()),'tongue_pixels':int(tongue.sum())}
    for name,a in parts.items():
        full=Image.new('RGBA',SIZE);full.paste(Image.fromarray(a),BOX[:2]);full.save(OUT/'layers'/f'Mouth_{name}.png')
    return parts,neutral,line,top,low,report


def pose(parts,neutral,line,top,low,p):
    if p==0:return {'Neutral':neutral.copy()}
    yy=np.broadcast_to(np.arange(neutral.shape[0])[:,None],neutral.shape[:2]).astype('float32')
    # Keep the opening anchor inside the final aperture at its tapered corners.
    # The original closed smile otherwise lies up to 0.82 px outside it, causing
    # a single antialiased corner pixel to fade while the opening expands.
    anchor=np.clip(line,top,low)
    upper=anchor*(1-p)+top*p;lower=anchor*(1-p)+low*p
    opening=np.minimum(np.clip(yy-upper+.5,0,1),np.clip(lower-yy+.5,0,1))
    result={n:a.copy() for n,a in parts.items()}
    result['Cavity'][:,:,3]=np.rint(result['Cavity'][:,:,3]*opening)
    # Anatomy stays in place behind the moving lip aperture. Teeth and tongue
    # emerge through clipping, without stretching the closed smile line.
    result['UpperLip']=remap_rgba(parts['UpperLip'],yy-(upper-top))
    result['LowerLip']=remap_rgba(parts['LowerLip'],yy-(lower-low))
    return result


def composite_pose(components):
    if 'Neutral' in components:return Image.fromarray(components['Neutral'])
    base=components['Cavity'].copy()
    out=Image.fromarray(base)
    for name in ['Teeth','Tongue']:
        out.alpha_composite(Image.fromarray(components[name]))
    # A PSD clipping stack composites its internal colors with source-over,
    # then uses the base layer's alpha for the complete stack. Preserve that
    # behavior at partially transparent cavity edges as well as solid pixels.
    out.putalpha(Image.fromarray(base[:,:,3]))
    for n in ['UpperLip','LowerLip']:out.alpha_composite(Image.fromarray(components[n]))
    return out


def main():
    for folder in ['qa','layers','keyforms']:(OUT/folder).mkdir(parents=True,exist_ok=True)
    parts,neutral,line,top,low,registration=extract()
    # Render the actual saved head to retain the checked eye and hair refinements.
    psd=PSDImage.open(BLINK/'Rurino_Head_Blink_Materials_v034.psd')
    old_mouth=next(g for g in psd if g.name=='05_Neutral_Mouth')
    before=psd.composite(force=True)
    old_mouth.visible=False;base=psd.composite(force=True)
    report={'scope':'frontal mouth material study; no audio or Cubism lip-sync',
            'registration':registration,'poses':[]}
    allowed=np.zeros((2048,2048),bool);allowed[BOX[1]:BOX[3],BOX[0]:BOX[2]]=True
    reference=np.array(before);grid=Image.new('RGB',(1800,310),(225,229,237));d=ImageDraw.Draw(grid)
    snapshots={}
    for i,p in enumerate([0,.25,.5,.75,1]):
        components=pose(parts,neutral,line,top,low,p)
        rendered=base.copy();rendered.alpha_composite(composite_pose(components),BOX[:2])
        a=np.array(rendered);error=np.abs(a.astype('int16')-reference.astype('int16'))
        assert error[~allowed].max()==0
        assert error[:,:,3].max()<=1
        assert np.array_equal(a[:,:,3]>127,reference[:,:,3]>127)
        if p==0:assert error[:,:,:3][reference[:,:,3]>0].max()<=1
        rendered.save(OUT/'keyforms'/f'mouth-open-{p:.2f}.png')
        tile=thumbnail(rendered.crop((790,960,1250,1270)),(360,245),(225,229,237));grid.paste(tile,(i*360,45));d.text((i*360+12,16),f'Mouth openness {p:.2f}',fill=(40,45,60))
        report['poses'].append({'openness':p,'outside_mouth_roi_max_change':int(error[~allowed].max()),
                               'alpha_change_max':int(error[:,:,3].max()),
                               'aperture_alpha_sum':int(components['Cavity'][:,:,3].sum()) if p else 0})
        if p in [.25,.5,1]:snapshots[p]=components
    grid.save(OUT/'qa/mouth-keyforms.jpg',quality=96)
    # Smooth amplitude study only; the sequence is not aligned to speech audio.
    sequence=[0]*14+[.06,.15,.3,.5,.7,.9,1,.8,.55,.3,.12,0]+[0]*5+[.08,.22,.4,.55,.35,.18,.05,0]+[0]*12
    frames=[]
    for p in sequence:
        mouth=composite_pose(pose(parts,neutral,line,top,low,p))
        if 0<p<.12:
            # Blend only the subpixel closure transition, after compositing on
            # skin, so two translucent lip outlines never darken each other.
            closed=base.copy();closed.alpha_composite(Image.fromarray(neutral),BOX[:2])
            opened=base.copy();opened.alpha_composite(mouth,BOX[:2])
            rendered=Image.blend(closed,opened,p/.12)
        else:
            rendered=base.copy();rendered.alpha_composite(mouth,BOX[:2])
        tile=thumbnail(rendered.crop((380,180,1660,1400)),(640,640),(225,229,237))
        ImageDraw.Draw(tile).text((12,10),'MOUTH MATERIAL STUDY / NO AUDIO OR RIG',fill=(40,45,60));frames.append(tile)
    preview=OUT/'qa/mouth-material-check.png'
    frames[0].save(preview,save_all=True,append_images=frames[1:],duration=60,loop=0,disposal=0,blend=0)
    with Image.open(preview) as animation:
        expanded=[]
        for k in range(animation.n_frames):
            animation.seek(k);expanded.extend([np.array(animation.convert('RGB'))]*round(animation.info['duration']/60))
    assert np.array_equal(np.stack(expanded),np.stack([np.array(f) for f in frames]))
    report['apng_lossless']=True
    old_mouth.visible=True
    state_groups={0:old_mouth}
    for p,components in snapshots.items():
        label={.25:'Small',.5:'Half',1:'Open'}[p]
        group=Group.new(f'05_Mouth_{label}_ENABLE_ONLY_ONE_MOUTH_GROUP',parent=psd);group.visible=False
        psd.remove(group);psd.insert(psd.index(old_mouth)+1,group)
        state_groups[p]=group
        for name,a in components.items():
            im=Image.fromarray(a);box=im.getbbox()
            assert box is not None
            full=Image.new('RGBA',SIZE);full.paste(im,BOX[:2]);full.save(OUT/'layers'/f'Mouth_{name}_{label}.png')
            layer=PixelLayer.frompil(im.crop(box),psd_file=psd,layer_name=f'Mouth_{name}_{label}',
                                     top=BOX[1]+box[1],left=BOX[0]+box[0]);group.append(layer)
            if name in ['Teeth','Tongue']:layer.clipping_layer=True
    path=OUT/'Rurino_Head_Eyes_and_Mouth_Materials_v034.psd';psd.save(path)
    del psd,state_groups;gc.collect();psd=PSDImage.open(path)
    checks=[]
    for p,label in [(0,'Neutral'),(.25,'Small'),(.5,'Half'),(1,'Open')]:
        for g in psd:
            if g.name.startswith('05_'):g.visible=('Neutral_Mouth' in g.name if p==0 else f'Mouth_{label}_' in g.name)
        actual=np.array(psd.composite(force=True));expected=np.array(Image.open(OUT/'keyforms'/f'mouth-open-{p:.2f}.png'))
        err=np.abs(actual.astype('int16')-expected.astype('int16'));visible=expected[:,:,3]>0
        maxrgb=int(err[:,:,:3][visible].max());maxalpha=int(err[:,:,3].max())
        checks.append({'state':label,'max_visible_rgb_error':maxrgb,'max_alpha_error':maxalpha})
        assert maxrgb<=5 and maxalpha<=1,checks
        Image.fromarray(actual).save(OUT/'qa'/f'psd-mouth-{label.lower()}.png')
    def walk(g):
        for child in g:
            if child.is_group():yield from walk(child)
            else:yield child
    leaves=list(walk(psd));assert len(leaves)==54 and len(set(l.name for l in leaves))==54
    assert sum(l.clipping_layer for l in leaves)==10
    report['saved_psd_checks']=checks;report['layer_count']=len(leaves)
    report['psd_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    report['limitations']=['one frontal open-mouth family, not vowel-specific visemes',
                           'no audio alignment, Cubism mesh or exported runtime model',
                           'head X/Y perspectives and full-body rig remain pending']
    (OUT/'qa/checks.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
