"""Repair the existing left-view fringe silhouette, then update its eye overlaps.

This is source-pixel restoration and local raster contour editing, not a new
character image or a Cubism rig. The continuous middle fringe is not
subdivided into arbitrary new strips. Shared upper-root ownership is unchanged.
"""
import argparse, gc, json, re
from pathlib import Path
import cv2
import numpy as np
from scipy.ndimage import distance_transform_edt, binary_fill_holes
from PIL import Image, ImageDraw, ImageFont
from psd_tools import PSDImage
from psd_tools.api.layers import Group, PixelLayer
from outline_hair_layers_v34 import (
    ROOT, W, H, DX, FONT, pixels, copy_pixel, paste_full, ink_image,
    tiled, set_state, checker, sha,
)

SOURCE = ROOT/'rebuild_v3_4/turn_redraw/hair_independent_ink/Rurino_Hair_Independent_Ink_v034.psd'
DONOR = ROOT/'rebuild_v3_4/turn_redraw/whole_hair_static_completion/inputs/source-context-reference.png'
OUT = ROOT/'rebuild_v3_4/turn_redraw/bangs_contour_repair'
PSD = OUT/'Rurino_Bangs_Contour_Repaired_v034.psd'
# Work in a bounded crop, with coordinates in the original 2048-pixel image.
BOX = (520,80,1530,940)
SIZE = (BOX[2]-BOX[0], BOX[3]-BOX[1])

def curve_mask(path):
    tokens=re.findall(r'[MLCQZ]|-?\d+(?:\.\d+)?',path)
    points=[];p=np.zeros(2);i=0
    while i<len(tokens):
        op=tokens[i];i+=1;n={'M':2,'L':2,'Q':4,'C':6,'Z':0}[op]
        v=np.array([float(x) for x in tokens[i:i+n]]).reshape(-1,2);i+=n
        if op in ('M','L'):p=v[0];points.append(p)
        elif op in ('C','Q'):
            for t in np.linspace(0,1,160)[1:]:
                points.append((1-t)**2*p+2*(1-t)*t*v[0]+t*t*v[1] if op=='Q' else (1-t)**3*p+3*(1-t)**2*t*v[0]+3*(1-t)*t*t*v[1]+t**3*v[2])
            p=v[-1]
    im=Image.new('L',(SIZE[0]*4,SIZE[1]*4))
    ImageDraw.Draw(im).polygon([((x-BOX[0])*4,(y-BOX[1])*4) for x,y in points],fill=255)
    return np.array(im.resize(SIZE,Image.Resampling.LANCZOS))

def cropped(layer):
    im=Image.new('RGBA',SIZE);im.paste(layer.topil().convert('RGBA'),(layer.left-DX-BOX[0],layer.top-BOX[1]));return np.array(im)

def put_crop(full,arr):
    out=full.copy();out.paste(Image.fromarray(arr),(DX+BOX[0],BOX[1]));return out

def panel(items,path,box,scale=1):
    font=ImageFont.truetype(FONT,23);small=ImageFont.truetype(FONT,18)
    tw=round((box[2]-box[0])*scale);th=round((box[3]-box[1])*scale)
    sheet=Image.new('RGB',(len(items)*(tw+20),th+105),'#e8edf3');d=ImageDraw.Draw(sheet)
    for i,(title,im) in enumerate(items):
        view=im.crop(box).resize((tw,th),Image.Resampling.LANCZOS)
        bg=checker(view.size);bg.paste(view,(0,0),view)
        x=i*(tw+20)+10;sheet.paste(bg,(x,52));d.text((x,12),title,font=font,fill='#26394c')
    d.text((15,th+68),'同一视角、同一比例；本轮修轮廓和发尖，尚未绑定 Live2D 动作。',font=small,fill='#52647a')
    sheet.save(path,quality=97)

def prepare():
    for folder in ['layers','masks','qa']:(OUT/folder).mkdir(parents=True,exist_ok=True)
    psd=PSDImage.open(SOURCE);old={l.name:l for l in pixels(psd)}
    a=cropped(old['Crown']);orig=a.copy();y,x=np.indices(a.shape[:2]);y+=BOX[1];x+=BOX[0]
    # Rejoin the serrated centre/right tips with continuous, unequal Béziers.
    # The upper part of the shape is a selection scaffold, not a cut in the PSD.
    tip_path=('M 860 240 C 905 350 948 520 963 626 '
      'C 976 704 949 754 940 776 C 981 740 993 647 987 521 '
      'C 1018 577 1098 679 1094 753 C 1125 724 1147 674 1153 634 '
      'C 1156 683 1146 747 1137 780 C 1170 753 1194 714 1202 684 '
      'C 1224 765 1223 817 1180 884 C 1266 801 1283 606 1254 473 '
      'C 1244 422 1227 386 1212 354 L 1180 220 Z')
    shape=curve_mask(tip_path)
    # Blend the contour change into the unedited upper hair over 80px.
    t=np.clip((y-470)/80,0,1);t=t*t*(3-2*t);t*=(x>900)&(x<1290)
    alpha=np.rint(orig[:,:,3]*(1-t)+shape*t).astype('uint8')
    # Repair the left hidden root notch, using actual underlying source hair.
    closed=cv2.morphologyEx(orig[:,:,3],cv2.MORPH_CLOSE,cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(37,37)))
    notch=(x>550)&(x<650)&(y>350)&(y<500)
    alpha[notch]=np.maximum(alpha[notch],closed[notch])
    donor=np.array(Image.open(DONOR).convert('RGBA').crop(BOX))
    added_notch=notch&(alpha>orig[:,:,3]);a[added_notch,:3]=donor[added_notch,:3]
    # Remove old cut-line fragments at the edited silhouette before redrawing.
    olddepth=cv2.distanceTransform((orig[:,:,3]>127).astype('uint8'),cv2.DIST_L2,5)
    lum=orig[:,:,:3].astype(float).mean(axis=2)
    interior=(olddepth>14)&(lum>170)&(orig[:,:,0]>190)
    nearest=distance_transform_edt(~interior,return_distances=False,return_indices=True)
    extended=orig[:,:,:3][nearest[0],nearest[1]]
    fill=(orig[:,:,3]<200)&(alpha>0)&(t>0)
    a[fill,:3]=extended[fill]
    newdepth=cv2.distanceTransform((alpha>127).astype('uint8'),cv2.DIST_L2,5)
    extended=cv2.GaussianBlur(extended,(0,0),3)
    recoat=np.maximum(np.clip((20-olddepth)/7,0,1),np.clip((16-newdepth)/6,0,1))*t*(alpha>0)
    a[:,:,:3]=np.rint(a[:,:,:3]*(1-recoat[:,:,None])+extended*recoat[:,:,None]).astype('uint8')
    a[:,:,3]=alpha;a[alpha==0]=0
    # Continue the scalp root underneath the right flower along a curved
    # silhouette. The old mask followed petal cut-outs and retained petal ink.
    # This concealed extension is inferred hair paint, not recovered flowers.
    rootshape=curve_mask('M 1230 130 C 1350 165 1405 250 1440 350 C 1470 420 1495 470 1485 510 C 1460 550 1410 585 1380 581 C 1355 565 1340 520 1310 480 C 1280 440 1250 420 1220 390 L 1220 130 Z')
    rootweight=np.clip((x-1300)/40,0,1)*np.clip((y-170)/30,0,1)*np.clip((510-y)/35,0,1)
    u=np.clip((x-(1200+.5*y))/180,0,1)
    rootcolour=np.array([250,233,195])+u[:,:,None]*np.array([-20,-31,-2])
    rootpaint=np.clip((24-olddepth)/14,0,1)*rootweight*(a[:,:,3]>0)
    a[:,:,:3]=np.rint(a[:,:,:3]*(1-rootpaint[:,:,None])+rootcolour*rootpaint[:,:,None]).astype('uint8')
    # Extra concealed root paint goes BEHIND the side locks, so it cannot
    # cap their visible flow lines. Preserve the original front alpha here.
    rootback=np.zeros_like(a);rootback[:,:,:3]=np.rint(rootcolour).astype('uint8');rootback[:,:,3]=rootshape;rootback[rootshape==0]=0
    rootchanges=int(((rootshape>0)&(a[:,:,3]==0)).sum())
    line=np.array(ink_image(Image.fromarray(a),2.8,'Crown',(DX+BOX[0],BOX[1])))
    # Reconnect the original mauve flow strokes to the new fork endpoints.
    # Draw into the colour material; the outer editable black ink stays separate.
    join=Image.new('RGBA',(SIZE[0]*4,SIZE[1]*4));jd=ImageDraw.Draw(join)
    for points in [[(1157,606),(1158,618),(1155,628),(1153,636)],[(1205,653),(1203,667),(1199,675),(1202,686)]]:
        p0,p1,p2,p3=np.array(points,float);prev=None
        for u in np.linspace(0,1,100):
            p=(1-u)**3*p0+3*(1-u)**2*u*p1+3*(1-u)*u*u*p2+u**3*p3
            if prev is not None:
                opacity=round(235*min(u*5,1));c=np.rint(np.array([111,83,99])*(1-u*.85)).astype(int)
                jd.line(((prev[0]-BOX[0])*4,(prev[1]-BOX[1])*4,(p[0]-BOX[0])*4,(p[1]-BOX[1])*4),fill=(*c,opacity),width=round((3.6-u*.8)*4))
            prev=p
    j=np.array(join.resize(SIZE,Image.Resampling.LANCZOS));j[:,:,3]=np.minimum(j[:,:,3],a[:,:,3])
    painted=np.array(Image.alpha_composite(Image.fromarray(a),Image.fromarray(j)))
    a[:,:,:3]=painted[:,:,:3]
    changed={
      'Crown':put_crop(paste_full(old['Crown'].topil().convert('RGBA'),old['Crown'].offset),a),
      'Ink_Crown':put_crop(paste_full(old['Ink_Crown'].topil().convert('RGBA'),old['Ink_Crown'].offset),line),
    }
    changed['Crown_ConcealedRoot_Underlap_LOCAL']=put_crop(Image.new('RGBA',(W,H)),rootback)
    # The previous face was cut to the old hair silhouette. Supply only the
    # narrow newly exposed skin margin underneath the revised fringe; eyes
    # remain above this patch, and original face/eye layers remain unchanged.
    skin=cropped(old['FacePaint_AfterCheekRecovery_SOURCE'])
    good=(skin[:,:,3]>220)&(skin[:,:,0]>230)&(skin[:,:,1]>190)&(skin[:,:,2]>180)
    near=distance_transform_edt(~good,return_distances=False,return_indices=True)
    skincolour=cv2.GaussianBlur(skin[:,:,:3][near[0],near[1]],(0,0),5)
    oldfront=cropped(old['RightFringe_ForegroundTips_SOURCE'])
    reveal=((orig[:,:,3]>0)|(oldfront[:,:,3]>0))&(a[:,:,3]<255)&(t>0)
    # A small dark source fleck inside the old inter-tip gap is contextual
    # residue rather than an eye feature. Restore skin below the eyelid layers.
    fleck=curve_mask('M 1123 701 C 1139 705 1150 715 1155 742 L 1126 754 L 1117 731 Z')>0
    support=cv2.dilate((reveal|fleck).astype('uint8'),np.ones((7,7),np.uint8))
    backing=np.zeros_like(a);backing[:,:,:3]=skincolour;backing[:,:,3]=support*255;backing[backing[:,:,3]==0]=0
    changed['Fringe_Edge_Skin_Underlap_LOCAL']=put_crop(Image.new('RGBA',(W,H)),backing)
    # Update the actual eye-front copy, not only the buried main hair layer.
    # A vertical fade starts above every eyelid's bounding box. No old tip can
    # survive below it; clipped portions use the same parent colour and ink.
    for n,region in [('Left_Fringe_EyeOverlap_SOURCE',(x<800)),('RightFringe_ForegroundTips_SOURCE',(x>900))]:
        fade=np.clip((y-680)/20,0,1)*region
        fg=a.copy();fg[:,:,3]=np.rint(fg[:,:,3]*fade).astype('uint8');fg[fg[:,:,3]==0]=0
        fgink=line.copy();fgink[:,:,3]=np.rint(fgink[:,:,3]*fade).astype('uint8');fgink[fgink[:,:,3]==0]=0
        empty=Image.new('RGBA',(W,H))
        changed[n]=put_crop(empty,fg);changed['Ink_Overlap_'+n]=put_crop(empty,fgink)
    for n,im in changed.items():im.save(OUT/'layers'/(n+'.png'))
    for n,m in [('fringe-new-alpha',a[:,:,3]),('tip-contour-edit',np.rint(t*255).astype('uint8'))]:
        Image.fromarray(m).save(OUT/'masks'/(n+'.png'))
    before=Image.alpha_composite(paste_full(old['Crown'].topil().convert('RGBA'),old['Crown'].offset),paste_full(old['Ink_Crown'].topil().convert('RGBA'),old['Ink_Crown'].offset))
    after=Image.alpha_composite(changed['Crown_ConcealedRoot_Underlap_LOCAL'],Image.alpha_composite(changed['Crown'],changed['Ink_Crown']));after.save(OUT/'qa/bangs-isolated.png')
    panel([('修改前 · 刘海原片',before),('修改后 · 连续轮廓与发尖',after)],OUT/'qa/bangs-contour-comparison.jpg',(DX+530,80,DX+1510,920),.8)
    panel([('修改前 · 断口与碎线',before),('修改后 · 发尖连接',after)],OUT/'qa/bangs-tips-detail.jpg',(DX+920,510,DX+1290,900),1.5)
    report={'source_sha256':sha(SOURCE),'donor_sha256':sha(DONOR),'tip_alpha_changed_pixels':int(((alpha!=orig[:,:,3])&(t>0)).sum()),'left_notch_recovered_pixels':int(added_notch.sum()),'upper_shared_root_ownership_unchanged':True,'right_root_new_backing_pixels':rootchanges,'root_backing_behind_side_locks':True,'right_root_inferred_under_flower':True,'flow_line_joins_reconnected':2,'repainted_contour_pixels':int((recoat>0).sum()),'changed_layers':list(changed),'method':'smooth tip and hidden root contour reconstruction, two flow-line joins; root layer ownership retained; boundary colour extension inferred from neighbouring hair','not_a_new_angle_or_rig':True}
    (OUT/'edit-record.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)

def build():
    source=PSDImage.open(SOURCE);old={l.name:l for l in pixels(source)}
    files={p.stem:p for p in (OUT/'layers').glob('*.png')}
    psd=PSDImage.new('RGBA',(W,H),color=0)
    def clone(items,parent):
        for item in items:
            if item.is_group():
                g=Group.new(item.name,parent=parent);g.visible=item.visible;g.opacity=item.opacity
                if item.blend_mode is not None:g.blend_mode=item.blend_mode
                if item.name=='01e_HeadHair':
                    n='Crown_ConcealedRoot_Underlap_LOCAL';im=Image.open(files[n]).convert('RGBA');b=im.getbbox()
                    g.append(PixelLayer.frompil(im.crop(b),psd_file=psd,layer_name=n,top=b[1],left=b[0]))
                clone(item,g)
                if item.name=='01d_Face_Ear':
                    n='Fringe_Edge_Skin_Underlap_LOCAL';im=Image.open(files[n]).convert('RGBA');b=im.getbbox()
                    g.append(PixelLayer.frompil(im.crop(b),psd_file=psd,layer_name=n,top=b[1],left=b[0]))
            elif item.name in files:
                im=Image.open(files[item.name]).convert('RGBA');b=im.getbbox()
                n=PixelLayer.frompil(im.crop(b),psd_file=psd,layer_name=item.name,top=b[1],left=b[0]);parent.append(n)
                n.visible=item.visible;n.opacity=item.opacity;n.blend_mode=item.blend_mode;n.clipping_layer=item.clipping_layer
            else:copy_pixel(item,parent,psd)
    clone(source,psd);set_state(psd,'Open');default=tiled(psd)
    default.save(OUT/'qa/bangs-assembled-Open.png');print('Rendered default',flush=True)
    psd._update_record();psd._record.image_data.set_data([ch.tobytes() for ch in default.split()],psd._record.header)
    with PSD.open('wb') as f:psd._record.write(f)
    del psd;gc.collect();saved=PSDImage.open(PSD);new={l.name:l for l in pixels(saved)}
    preserved=[]
    for n,l in old.items():
        q=new[n]
        assert (l.visible,l.opacity,l.blend_mode,l.clipping_layer)==(q.visible,q.opacity,q.blend_mode,q.clipping_layer),n
        if n not in files:
            assert l.offset==q.offset and np.array_equal(np.array(l.topil()),np.array(q.topil())),n
            preserved.append(n)
        else:
            im=Image.open(files[n]);b=im.getbbox();assert tuple(q.bbox)==b
            assert np.array_equal(np.array(q.topil().convert('RGBA')),np.array(im.crop(b))),n
    for n in set(files)-set(old):
        im=Image.open(files[n]);b=im.getbbox();assert tuple(new[n].bbox)==b
        assert np.array_equal(np.array(new[n].topil().convert('RGBA')),np.array(im.crop(b))),n
    assert np.array_equal(np.array(default),np.array(tiled(saved)))
    states=[]
    for state in ['Open','Half','Closed']:
        set_state(saved,state);im=default if state=='Open' else tiled(saved)
        path=OUT/'qa'/('bangs-assembled-'+state+'.png');im.save(path);states.append({'name':state,'sha256':sha(path)})
        print('Verified',state,flush=True)
    a=np.array(Image.open(files['Crown']));m=a[:,:,3]>127
    count,_,stats,_=cv2.connectedComponentsWithStats(m.astype('uint8'),8)
    major=int((stats[1:,cv2.CC_STAT_AREA]>8).sum());holes=int((binary_fill_holes(m)&~m).sum())
    assert major==1 and holes==0,(major,holes)
    report=json.loads((OUT/'edit-record.json').read_text())
    report.update({'psd':PSD.name,'sha256':sha(PSD),'source_psd':str(SOURCE.relative_to(ROOT)),'canvas':[W,H],'pixel_layers':len(new),'unchanged_layers':preserved,'unchanged_rgba_offsets_properties_exact':True,'edited_layers_roundtrip_exact':True,'saved_default_matches_preview':True,'fringe_connected_components_over_8px':major,'fringe_enclosed_hole_pixels':holes,'states':states,'scope':'current left-view raster material; no Cubism motion or new runtime model'})
    (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    before=Image.open(SOURCE.parent/'qa/ink-assembled-Open.png').convert('RGBA')
    ba=np.array(before)[:,:,3];aa=np.array(default)[:,:,3]
    assert not np.any((ba>250)&(aa<240)), 'newly exposed transparency'
    report['new_transparent_gaps_under_repaired_fringe']=0
    (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    panel([('修改前',before),('修改后',default)],OUT/'qa/bangs-head-comparison.jpg',(DX+400,80,DX+1450,1150),.65)
    views=[({'Open':'睁眼','Half':'半闭眼','Closed':'闭眼'}[s],Image.open(OUT/'qa'/('bangs-assembled-'+s+'.png')).convert('RGBA')) for s in ['Open','Half','Closed']]
    panel(views,OUT/'qa/bangs-eye-states.jpg',(DX+400,80,DX+1450,1150),.45)
    print(json.dumps({'psd':str(PSD),'preserved':len(preserved),'changed':len(files),'sha256':sha(PSD)},indent=2),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--build',action='store_true');args=parser.parse_args()
    if args.build:build()
    else:prepare()
