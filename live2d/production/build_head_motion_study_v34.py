"""Bounded shared-coordinate head motion study; not a Cubism model.

An orthographic 2.5D proxy gives ALL visible head materials the same map.
No independent face/eye scale or translation is used. Hidden surfaces and
changes in occlusion are not modeled; the proxy is limited to small angles.
"""
import hashlib
import json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image,ImageDraw
from build_expression_materials_v34 import remap_rgba,form_components,source_components
from build_mouth_materials_v34 import composite_pose,BOX
from split_head_v34 import thumbnail

ROOT=Path(__file__).resolve().parents[1]
EXP=ROOT/'rebuild_v3_4/expression_refinement'
MOUTH=ROOT/'rebuild_v3_4/mouth_refinement'
OUT=ROOT/'rebuild_v3_4/head_motion_study'
CX,CY=1020.,800.
LIMIT_X,LIMIT_Y=8.,5.
STILL_Y=1480


def forward(x,y,yaw,pitch):
    """Input/output in original 2048-pixel coordinates; positive yaw is right."""
    assert abs(yaw)<=LIMIT_X+1e-6 and abs(pitch)<=LIMIT_Y+1e-6
    t=np.deg2rad(yaw);p=np.deg2rad(pitch)
    u=x-CX;v=y-CY
    depth=220*np.exp(-(u/460)**2)*np.exp(-((y-850)/1000)**4)
    taper=np.clip((y-1280)/200,0,1)
    weight=1-taper*taper*(3-2*taper)
    rx=np.cos(t)*u+np.sin(t)*depth
    rz=-np.sin(t)*u+np.cos(t)*depth
    ry=np.cos(p)*v-np.sin(p)*rz
    return x+weight*(rx-u),y+weight*(ry-v)


def inverse(x,y,yaw,pitch):
    sx=x.copy();sy=y.copy()
    for _ in range(10):
        fx,fy=forward(sx,sy,yaw,pitch)
        sx+=x-fx;sy+=y-fy
    return sx,sy


def warp(a,yaw,pitch):
    if yaw==0 and pitch==0:return a.copy()
    scale=2048/a.shape[0]
    yy,xx=np.mgrid[:a.shape[0],:a.shape[1]].astype('float32')
    # Pixel centers retain the same physical origin at preview resolution.
    xx=(xx+.5)*scale-.5;yy=(yy+.5)*scale-.5
    sx,sy=inverse(xx,yy,yaw,pitch)
    result=remap_rgba(a,(sx+.5)/scale-.5,(sy+.5)/scale-.5)
    # The map is exactly identity here. Copy rather than resampling to retain
    # original bytes, including arbitrary RGB stored under fully clear pixels.
    cutoff=int(np.ceil((STILL_Y+.5)/scale-.5))
    result[cutoff:]=a[cutoff:]
    return result


def mesh_and_checks(yaw,pitch):
    coords=np.linspace(0,2047,65)
    xx,yy=np.meshgrid(coords,coords)
    fx,fy=forward(xx,yy,yaw,pitch)
    sx,sy=inverse(fx,fy,yaw,pitch)
    inverse_error=float(np.hypot(sx-xx,sy-yy).max())
    assert inverse_error<.01
    # Signed area of both triangles in each control cell detects folds.
    points=np.stack([fx,fy],axis=2)
    a=points[:-1,:-1];b=points[:-1,1:];c=points[1:,:-1];d=points[1:,1:]
    def cross(u,v):return u[:,:,0]*v[:,:,1]-u[:,:,1]*v[:,:,0]
    area=np.concatenate([cross(b-a,c-a).ravel(),cross(d-b,c-b).ravel()])
    area/=((2047/64)**2)
    assert area.min()>.7,(yaw,pitch,area.min())
    # Independent measured eye centers and cheek outline endpoints.
    anchors=np.array([[817.884689,844.179718],[1222.764252,842.129379],
                      [719.,980.],[1326.,980.],[1020.,980.],[1019.5,1101.],[1020.,1270.]])
    ax,ay=forward(anchors[:,0],anchors[:,1],yaw,pitch)
    transformed=np.stack([ax,ay],axis=1)
    ratio=lambda q:np.linalg.norm(q[1]-q[0])/np.linalg.norm(q[3]-q[2])
    ratio_change=abs(ratio(transformed)/ratio(anchors)-1)
    assert ratio_change<.01,(yaw,pitch,ratio_change)
    face_width_ratio=np.linalg.norm(transformed[3]-transformed[2])/np.linalg.norm(anchors[3]-anchors[2])
    assert .97<face_width_ratio<1.01
    bottom=yy>=STILL_Y
    assert np.array_equal(fx[bottom],xx[bottom]) and np.array_equal(fy[bottom],yy[bottom])
    record={'yaw_proxy_degrees':yaw,'pitch_proxy_degrees':pitch,
            'inverse_error_max_px':inverse_error,'mesh_min_signed_area_ratio':float(area.min()),
            'eye_spacing_to_cheek_width_relative_change':float(ratio_change),
            'cheek_width_ratio':float(face_width_ratio),'below_y1480_exactly_fixed':True,
            'landmark_names':['iris_L','iris_R','cheek_L','cheek_R','nose','mouth','chin'],
            'projected_landmarks':np.round(transformed,4).tolist()}
    return {'grid_size':[65,65],'source_grid_spacing':2047/64,
            'destination_xy':np.round(points,4).tolist()},record


def save_animation(frames,path,duration=100):
    frames[0].save(path,save_all=True,append_images=frames[1:],duration=duration,loop=0,disposal=0,blend=0)
    with Image.open(path) as animation:
        index=0
        for k in range(animation.n_frames):
            animation.seek(k);actual=np.array(animation.convert('RGB'))
            for _ in range(round(animation.info['duration']/duration)):
                assert np.array_equal(actual,np.array(frames[index]));index+=1
        assert index==len(frames)


def main():
    for d in ['keyforms','qa','meshes']:(OUT/d).mkdir(parents=True,exist_ok=True)
    neutral=np.array(Image.open(EXP/'keyforms/Default_Closed.png').convert('RGBA'))
    report={'scope':'shared-coordinate 2.5D raster/mesh study; not Cubism binding or true multi-view artwork',
            'source_psd_sha256':hashlib.sha256((EXP/'Rurino_Head_Expression_Materials_v034.psd').read_bytes()).hexdigest(),
            'limits':{'yaw_proxy_degrees':[-8,8],'pitch_proxy_degrees':[-5,5]},
            'pivot_xy':[CX,CY],'lower_transition_y':[1280,1480],'keyforms':[]}
    grid=Image.new('RGB',(1440,1470),(225,229,237));draw=ImageDraw.Draw(grid)
    for row,pitch in enumerate([-5,0,5]):
        for column,yaw in enumerate([-8,0,8]):
            mesh,check=mesh_and_checks(yaw,pitch)
            name=f'x{yaw:+03d}_y{pitch:+03d}'
            (OUT/'meshes'/f'{name}.json').write_text(json.dumps(mesh,separators=(',',':'))+'\n')
            arr=warp(neutral,yaw,pitch)
            assert np.array_equal(arr[STILL_Y:],neutral[STILL_Y:])
            if yaw==pitch==0:assert np.array_equal(arr,neutral)
            Image.fromarray(arr).save(OUT/'keyforms'/f'{name}.png')
            tile=thumbnail(Image.fromarray(arr).crop((320,100,1720,1460)),(480,455),(225,229,237))
            grid.paste(tile,(column*480,row*490+30));draw.text((column*480+12,row*490+10),f'X {yaw:+} / Y {pitch:+} - small-angle proxy',fill=(40,45,60))
            report['keyforms'].append(check)
            print(name,'checked',flush=True)
    grid.save(OUT/'qa/head-keyforms.jpg',quality=95)
    # All 231 parameter samples: the same geometry constraints apply between keys.
    dense=[]
    for yaw in np.linspace(-8,8,21):
        for pitch in np.linspace(-5,5,11):
            _,check=mesh_and_checks(float(yaw),float(pitch));dense.append(check)
    report['continuous_check']={'samples':len(dense),'minimum_mesh_signed_area_ratio':min(r['mesh_min_signed_area_ratio'] for r in dense),
        'max_eye_spacing_to_cheek_width_relative_change':max(r['eye_spacing_to_cheek_width_relative_change'] for r in dense),
        'max_inverse_error_px':max(r['inverse_error_max_px'] for r in dense)}
    # Preserve the exact body/skin baseline from a saved neutral composition;
    # replace only the mouth ROI using the known blank skin before head warping.
    from psd_tools import PSDImage
    psd=PSDImage.open(EXP/'Rurino_Head_Expression_Materials_v034.psd')
    for g in psd:
        if g.name.startswith('05_'):g.visible=False
    base=psd.composite(force=True)
    import gc
    del psd;gc.collect()
    frames=[];sequence=[(0.,0.,0.)]*6
    sequence += [(8*np.sin(t),0.,.65*np.sin(t)**2) for t in np.linspace(0,2*np.pi,33)]
    sequence += [(0.,5*np.sin(t),.5*np.sin(t)**2) for t in np.linspace(0,2*np.pi,25)]
    sequence += [(0.,0.,0.)]*6
    for yaw,pitch,form in sequence:
        head=base.copy();head.alpha_composite(composite_pose(form_components(source_components(0),form)),BOX[:2])
        source=np.array(head.resize((1024,1024),Image.Resampling.LANCZOS))
        animated=Image.fromarray(warp(source,float(yaw),float(pitch)))
        tile=thumbnail(animated.crop((160,50,860,730)),(640,640),(225,229,237))
        ImageDraw.Draw(tile).text((12,10),'SHARED HEAD MOTION STUDY / NOT A LIVE2D RIG',fill=(40,45,60));frames.append(tile)
    save_animation(frames,OUT/'qa/head-motion-check.png')
    report['apng_lossless']=True;report['animation_frames']=len(frames)
    report['limitations']=['shared flattened proxy: no hidden-side reconstruction or changed occlusion',
        'control grid is JSON reference, not an importable Cubism warp deformer',
        'original asymmetric hair retained; no independent ponytail physics',
        '76-layer PSD remains frontal; turned PNGs are flattened motion references',
        'no new cmo3/moc3, audio synchronization or Windows runtime']
    (OUT/'qa/checks.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report['continuous_check'],indent=2),flush=True)


if __name__=='__main__':main()
