"""Add restrained MouthForm reference states to the saved mouth material PSD.
These are editable raster keyforms, not Cubism parameter bindings.
"""
import gc
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image, ImageDraw
from psd_tools import PSDImage
from psd_tools.api.layers import Group, PixelLayer
from build_mouth_materials_v34 import BOX, SIZE, composite_pose
from split_head_v34 import thumbnail

ROOT=Path(__file__).resolve().parents[1]
MOUTH=ROOT/'rebuild_v3_4/mouth_refinement'
OUT=ROOT/'rebuild_v3_4/expression_refinement'


def remap_rgba(a,xmap,ymap):
    v=a.astype('float32')/255
    v[:,:,:3]*=v[:,:,3:4]
    out=cv2.remap(v,xmap.astype('float32'),ymap.astype('float32'),cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
    out[:,:,:3]/=np.maximum(out[:,:,3:4],1/65536)
    out=np.uint8(np.clip(np.rint(out*255),0,255))
    out[out[:,:,3]==0]=0
    return out


def source_components(openness):
    if openness==0:
        p=ROOT/'rebuild_v3_4/face_features/layers/Mouth_Neutral.png'
        return {'Neutral':np.array(Image.open(p).convert('RGBA').crop(BOX))}
    label={.5:'Half',1:'Open'}[openness]
    return {n:np.array(Image.open(MOUTH/'layers'/f'Mouth_{n}_{label}.png').convert('RGBA').crop(BOX))
            for n in ['Cavity','Teeth','Tongue','UpperLip','LowerLip']}


def form_components(components,form):
    if form==0:return {n:a.copy() for n,a in components.items()}
    yy,xx=np.mgrid[:BOX[3]-BOX[1],:BOX[2]-BOX[0]].astype('float32')
    center=(937+1102)/2-BOX[0]
    xmap=center+(xx-center)/(1+.025*form)
    u=np.clip((xmap-center)/82.5,-1.3,1.3)
    ymap=yy+6*form*u*u
    return {n:remap_rgba(a,xmap,ymap) for n,a in components.items()}


def main():
    for d in ['layers','keyforms','qa']:(OUT/d).mkdir(parents=True,exist_ok=True)
    psd=PSDImage.open(MOUTH/'Rurino_Head_Eyes_and_Mouth_Materials_v034.psd')
    original=psd.composite(force=True)
    for g in psd:
        if g.name.startswith('05_'):g.visible=False
    base=psd.composite(force=True)
    cases=[('Default_Closed',0,0)]+[(f'{formname}_{label}',form,openness)
        for formname,form in [('Relaxed',-1),('Smile',1)]
        for label,openness in [('Closed',0),('Half',.5),('Open',1)]]
    sheet=Image.new('RGB',(1440,700),(225,229,237));draw=ImageDraw.Draw(sheet)
    report={'scope':'restrained frontal MouthForm raster references, not bound',
            'source_psd_sha256':hashlib.sha256((MOUTH/'Rurino_Head_Eyes_and_Mouth_Materials_v034.psd').read_bytes()).hexdigest(),
            'form_parameters':{'corner_y_shift_px_at_full_form':6,'width_scale_range':[.975,1.025],
                               'center_x_global':1019.5},'cases':[]}
    neutral=np.array(original)
    for i,(name,form,opening) in enumerate(cases):
        components=form_components(source_components(opening),form)
        rendered=base.copy();rendered.alpha_composite(composite_pose(components),BOX[:2])
        rendered.save(OUT/'keyforms'/f'{name}.png')
        delta=np.abs(np.array(rendered).astype('int16')-neutral.astype('int16'))
        delta[BOX[1]:BOX[3],BOX[0]:BOX[2]]=0
        assert delta.max()==0
        if form==0:
            assert np.abs(np.array(rendered).astype('int16')-neutral.astype('int16')).max()<=1
            continue
        row=0 if form<0 else 1;column={0:0,.5:1,1:2}[opening]
        tile=thumbnail(rendered.crop((790,970,1250,1250)),(480,295),(225,229,237))
        sheet.paste(tile,(column*480,row*350+45));draw.text((column*480+12,row*350+15),name,fill=(40,45,60))
        group=Group.new(f'05_MouthForm_{name}_ENABLE_ONLY_ONE_MOUTH_GROUP',parent=psd)
        psd.remove(group);psd.insert(len(psd)-1,group);group.visible=False
        for part,a in components.items():
            im=Image.fromarray(a);bbox=im.getbbox();assert bbox
            full=Image.new('RGBA',SIZE);full.paste(im,BOX[:2]);full.save(OUT/'layers'/f'MouthForm_{part}_{name}.png')
            layer=PixelLayer.frompil(im.crop(bbox),psd_file=psd,layer_name=f'MouthForm_{part}_{name}',
                                     top=BOX[1]+bbox[1],left=BOX[0]+bbox[0]);group.append(layer)
            if part in ['Teeth','Tongue']:layer.clipping_layer=True
    sheet.save(OUT/'qa/mouth-form-keyforms.jpg',quality=96)
    next(g for g in psd if g.name=='05_Neutral_Mouth').visible=True
    path=OUT/'Rurino_Head_Expression_Materials_v034.psd';psd.save(path)
    del psd;gc.collect();psd=PSDImage.open(path)
    for name,form,opening in cases:
        for g in psd:
            if g.name.startswith('05_'):g.visible=(g.name=='05_Neutral_Mouth' if form==0 else g.name.startswith(f'05_MouthForm_{name}_'))
        actual=np.array(psd.composite(force=True));expected=np.array(Image.open(OUT/'keyforms'/f'{name}.png'))
        error=np.abs(actual.astype('int16')-expected.astype('int16'))
        maxrgb=int(error[:,:,:3][expected[:,:,3]>0].max());maxalpha=int(error[:,:,3].max())
        assert maxrgb<=3 and maxalpha<=1,(name,maxrgb,maxalpha)
        report['cases'].append({'name':name,'form':form,'opening':opening,'psd_visible_rgb_max_error':maxrgb,
                                'psd_alpha_max_error':maxalpha,'outside_mouth_roi_max_change':0})
        print(name,maxrgb,maxalpha,flush=True)
    # descendants() also traverses clipping references, so count the physical
    # group tree directly rather than counting clipped layers twice.
    def walk(group):
        for child in group:
            if child.is_group():yield from walk(child)
            else:yield child
    leaves=list(walk(psd))
    assert len(leaves)==76 and len(set(x.name for x in leaves))==76
    assert sum(x.clipping_layer for x in leaves)==18
    report['layer_count']=76;report['clipping_layer_count']=18
    report['psd_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    report['limitations']=['restrained smile/relaxed shape only; no vowel-specific visemes',
                          'no Cubism mesh, parameter binding, audio alignment or runtime model']
    (OUT/'qa/checks.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':main()
