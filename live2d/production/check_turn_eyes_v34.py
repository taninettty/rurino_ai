"""Visible-eye measurements and annotated comparisons, not a 3D pose solver.

Iris and sclera color masks measure visible drawing geometry. They do not
recover orbital centers, hidden eye corners, true yaw or a universal eye gap.
"""
import hashlib,json
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
TURN=ROOT/'rebuild_v3_4/turn_redraw'
OUT=TURN/'eye_calibration'
CASES={
 'left_before':{'path':TURN/'sources/turn-left-v2-source.png','rois':[(605,735,780,906),(930,735,1190,906)],'far_index':0,'nose_mark':[780,942]},
 'right_before':{'path':TURN/'sources/turn-right-source.png','rois':[(865,735,1120,906),(1260,740,1465,910)],'far_index':1,'nose_mark':[1264,948]},
 'official_left':{'path':OUT/'official-56.4s-close.png','rois':[(151,274,204,323),(245,274,322,324)],'far_index':0,'nose_mark':[210,349],'video_seconds':56.4},
 'official_right':{'path':OUT/'official-58.2s-close.png','rois':[(182,266,248,318),(289,259,326,310)],'far_index':1,'nose_mark':[284,337],'video_seconds':58.2},
}


def largest(mask):
    n,l,s,c=cv2.connectedComponentsWithStats(mask.astype('uint8'))
    assert n>1
    k=1+np.argmax(s[1:,4]);return l==k,s[k],c[k]


def measure(path,rois,far_index,nose_mark,**kwargs):
    a=np.array(Image.open(path).convert('RGB'));eyes=[]
    for x,y,r,b in rois:
        rgb=a[y:b,x:r].astype('int16');red,green,blue=rgb.transpose(2,0,1)
        iris,stats,center=largest((green-red>18)&(blue-red>16))
        assert stats[4]>80
        white=(np.abs(red-green)<10)&(np.abs(red-blue)<14)&(rgb.min(2)>115)
        eye,es,ec=largest(iris|white)
        eyes.append({'iris_bbox':[int(x+stats[0]),int(y+stats[1]),int(x+stats[0]+stats[2]),int(y+stats[1]+stats[3])],
                     'iris_centroid':[float(x+center[0]),float(y+center[1])],
                     'visible_fill_bbox':[int(x+es[0]),int(y+es[1]),int(x+es[0]+es[2]),int(y+es[1]+es[3])],
                     'iris_pixels':int(stats[4]),'touches_roi':bool(stats[0]==0 or stats[1]==0 or stats[0]+stats[2]>=r-x or stats[1]+stats[3]>=b-y)})
    far=eyes[far_index];near=eyes[1-far_index]
    width=lambda e:e['iris_bbox'][2]-e['iris_bbox'][0]
    height=lambda e:e['iris_bbox'][3]-e['iris_bbox'][1]
    l=np.array(eyes[0]['iris_centroid']);r=np.array(eyes[1]['iris_centroid']);distance=float(np.linalg.norm(r-l));axis=(r-l)/distance
    mid=(l+r)/2;offset=float(np.dot(np.array(nose_mark)-mid,axis)/distance)
    return {'file':str(path.relative_to(ROOT)),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'eyes':eyes,
            'far_near_visible_iris_width_ratio':width(far)/width(near),
            'far_near_visible_iris_aspect_ratio':(width(far)/height(far))/(width(near)/height(near)),
            'iris_center_distance_px':distance,'inner_visible_fill_gap_px':eyes[1]['visible_fill_bbox'][0]-eyes[0]['visible_fill_bbox'][2],
            'nose_mark_manual':nose_mark,'nose_offset_along_eye_axis_over_center_distance':offset,
            'note':'different pitch, eyelid openness and gaze: reference metrics are guides, not exact targets'}


def annotate(case,record):
    image=Image.open(case['path']).convert('RGBA');bg=Image.new('RGBA',image.size,(225,229,237,255));bg.alpha_composite(image);im=bg.convert('RGB');d=ImageDraw.Draw(im)
    scale=image.width/560;line=max(1,round(1.3*scale));dot=max(3,round(3*scale))
    centers=[]
    for i,e in enumerate(record['eyes']):
        color=(0,145,170) if i==case['far_index'] else (220,130,25)
        d.rectangle(e['iris_bbox'],outline=color,width=line)
        d.rectangle(e['visible_fill_bbox'],outline=(90,160,70),width=line)
        x,y=e['iris_centroid'];centers.append((x,y));d.ellipse((x-dot,y-dot,x+dot,y+dot),fill=color)
    d.line(centers,fill=(170,65,160),width=line)
    x,y=case['nose_mark'];d.line((x-dot*2,y,x+dot*2,y),fill=(185,45,65),width=line);d.line((x,y-dot*2,x,y+dot*2),fill=(185,45,65),width=line)
    # Crop around eyes and the nasal mark; common scale inside each before/after pair.
    x0=min(b[0] for b in case['rois'])-20;y0=min(b[1] for b in case['rois'])-25
    x1=max(b[2] for b in case['rois'])+20;y1=max(case['nose_mark'][1]+30,max(b[3] for b in case['rois']))
    crop=im.crop((x0,y0,x1,y1))
    factor=min(640/crop.width,300/crop.height)
    crop=crop.resize((round(crop.width*factor),round(crop.height*factor)),Image.Resampling.LANCZOS)
    tile=Image.new('RGB',(660,355),(225,229,237));tile.paste(crop,((660-crop.width)//2,38))
    return tile


def main():
    (OUT/'qa').mkdir(exist_ok=True)
    cases=dict(CASES)
    retained=[]
    for side in ['left','right']:
        path=OUT/'corrected'/f'turn-{side}-eye-calibrated.png'
        if path.exists():cases[side+'_after']={**CASES[side+'_before'],'path':path}
        else:
            cases[side+'_after']=dict(CASES[side+'_before'])
            retained.append(side+'_after')
    records={n:measure(**c) for n,c in cases.items()}
    sheet=Image.new('RGB',(1980,710),(225,229,237));draw=ImageDraw.Draw(sheet)
    for row,side in enumerate(['left','right']):
        for col,key in enumerate(['official_'+side,side+'_before',side+'_after']):
            if key not in records:continue
            tile=annotate(cases[key],records[key]);label=f'{key}: far/near iris width {records[key]["far_near_visible_iris_width_ratio"]:.3f}'
            if key in retained:label=key+': ORIGINAL RETAINED / correction pending'
            ImageDraw.Draw(tile).text((10,10),label,fill=(40,45,60));sheet.paste(tile,(col*660,row*355))
    sheet.save(OUT/'qa/eye-perspective-audit.jpg',quality=96)
    clean=Image.new('RGB',(1280,740),(225,229,237))
    for row,side in enumerate(['left','right']):
        # Same crop/scale for each before/after pair; never alters source files.
        box=(540,650,1260,1050) if side=='left' else (780,650,1500,1050)
        for col,suffix in enumerate(['before','after']):
            key=side+'_'+suffix
            if key not in cases:continue
            im=Image.open(cases[key]['path']).convert('RGBA').crop(box).resize((630,350),Image.Resampling.LANCZOS)
            clean.paste(im,(col*640+5,row*370+20),im)
            label=side.upper()+' / '+suffix.upper()
            if key in retained:label=side.upper()+' / ORIGINAL RETAINED - correction pending'
            ImageDraw.Draw(clean).text((col*640+12,row*370+4),label,fill=(40,45,60))
    clean.save(OUT/'qa/eye-before-after.jpg',quality=96)
    report={'method':'fixed-ROI largest iris color component; visible sclera+iris fill; manual nose mark',
            'color_thresholds':{'G_minus_R':18,'B_minus_R':16},'measurements':records,
            'original_retained_not_corrected':retained,
            'limits':['manual ROI and nose mark; low-resolution video; roughly 1-2 video pixels of boundary uncertainty',
                      'eye corners hidden by lashes/hair are not recovered; fill bounds are not true anatomical canthi',
                      'iris centroid is not the orbital center, and gaze can move it',
                      'no calibrated camera, true yaw or common fixed eye-distance ratio',
                      'no claim of Cubism runtime or animation validation']}
    (OUT/'qa/eye-measurements.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({n:{k:r[k] for k in ['far_near_visible_iris_width_ratio','iris_center_distance_px','inner_visible_fill_gap_px','nose_offset_along_eye_axis_over_center_distance']} for n,r in records.items()},indent=2))

if __name__=='__main__':main()
