"""Registered blink material keyforms and a raster study, not a Cubism rig.

Iris texture stays fixed. Eye-white aperture closes, upper lashes deform,
lower lashes approach the closing line. LibTV supplies the closed lash plate.
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
from scipy.ndimage import gaussian_filter1d, distance_transform_edt

from export_gaze_v34 import BASE, decode
from split_head_v34 import thumbnail

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT/'rebuild_v3_4/face_features'
OUT = ROOT/'rebuild_v3_4/blink_refinement'
SIZE = (2048, 2048)
BOXES = {'L': (640, 690, 970, 955), 'R': (1080, 690, 1410, 955)}


def component(alpha, rank=0):
    n, labels, stats, _ = cv2.connectedComponentsWithStats((alpha > 100).astype('uint8'))
    idx = sorted(range(1, n), key=lambda i: stats[i, 4], reverse=True)[rank]
    selected = cv2.dilate((labels == idx).astype('uint8'), np.ones((3, 3), np.uint8))
    return alpha * selected


def curves(alpha):
    top = []; bottom = []; columns = []
    for x in range(alpha.shape[1]):
        y = np.where(alpha[:, x] > 40)[0]
        if len(y):
            columns.append(x); top.append(y[0]); bottom.append(y[-1])
    xx = np.arange(alpha.shape[1])
    return (gaussian_filter1d(np.interp(xx, columns, top), 1),
            gaussian_filter1d(np.interp(xx, columns, bottom), 1))


def remap_rgba(a, ymap):
    """Premultiplied interpolation avoids dark halos at moving lash edges."""
    xmap = np.broadcast_to(np.arange(a.shape[1], dtype='float32'), a.shape[:2])
    v = a.astype('float32')/255
    v[:, :, :3] *= v[:, :, 3:4]
    out = cv2.remap(v, xmap, ymap.astype('float32'), cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_CONSTANT)
    out[:, :, :3] /= np.maximum(out[:, :, 3:4], 1/65536)
    return np.uint8(np.clip(np.rint(out*255), 0, 255))


def blend_rgba(a, b, t):
    aa = a.astype('float32')/255; bb = b.astype('float32')/255
    aa[:, :, :3] *= aa[:, :, 3:4]; bb[:, :, :3] *= bb[:, :, 3:4]
    out = aa*t + bb*(1-t)
    out[:, :, :3] /= np.maximum(out[:, :, 3:4], 1/65536)
    return np.uint8(np.clip(np.rint(out*255), 0, 255))


def morph_lashes(a, b, t):
    if t == 0: return b
    if t == 1: return a
    # Interpolate contours, not the visibility of two outlines: alpha crossfade
    # produces grey duplicate spikes near the outer eye corners.
    def sdf(im):
        m=(im[:, :, 3]>100).astype('uint8')
        return cv2.distanceTransform(m,cv2.DIST_L2,5)-cv2.distanceTransform(1-m,cv2.DIST_L2,5)
    alpha=np.clip(.5+t*sdf(a)+(1-t)*sdf(b),0,1)
    out=blend_rgba(a,b,t)
    out[:, :, 3]=np.rint(alpha*255)
    out[out[:, :, 3]==0]=0
    return out


def prepare_eye(side, parts, closed_source, blank):
    box = BOXES[side]
    eye = {suffix: np.array(parts[f'Eye_{side}_{suffix}'].crop(box))
           for suffix in ['White', 'Iris', 'UpperLid', 'LowerLid']}
    lash = eye['UpperLid'].copy(); lash[:, :, 3] = component(lash[:, :, 3])
    crease = eye['UpperLid'].copy(); crease[:, :, 3] = component(crease[:, :, 3], 1)
    generated = np.array(closed_source.crop(box)).astype('float32')
    skin = np.array(blank.crop(box)).astype('float32')
    # Take only the connected closed eyelash, excluding ear edges and folds.
    dark = ((generated[:, :, :3].max(2) < 135)*255).astype('uint8')
    dark = component(dark)
    support = cv2.dilate((dark > 0).astype('uint8'), np.ones((7, 7), np.uint8))
    alpha = np.clip((skin[:, :, :3].mean(2)-generated[:, :, :3].mean(2)) /
                    np.maximum(skin[:, :, :3].mean(2)-45, 1), 0, 1)*support
    closed = np.zeros_like(eye['UpperLid'])
    closed[:, :, :3] = np.clip(np.rint((generated[:, :, :3]-skin[:, :, :3]*(1-alpha[:, :, None])) /
                                      np.maximum(alpha[:, :, None], 1/255)), 0, 255)
    closed[:, :, 3] = np.rint(alpha*255)
    closed[closed[:, :, 3] == 0] = 0
    # Register the generated lash ends to the original lash span, preserving eye spacing.
    ox = np.where(lash[:, :, 3].max(0) > 100)[0]
    cx = np.where(closed[:, :, 3].max(0) > 100)[0]
    reg = np.zeros_like(closed)
    reg[:, ox[0]:ox[-1]+1] = np.array(Image.fromarray(closed[:, cx[0]:cx[-1]+1]).resize(
        (int(ox[-1]-ox[0]+1), closed.shape[0]), Image.Resampling.BICUBIC))
    closed = reg
    lt, lb = curves(lash[:, :, 3]); ct, cb = curves(closed[:, :, 3])
    lt,lb,ct,cb=[gaussian_filter1d(v,4) for v in [lt,lb,ct,cb]]
    # Extend opaque ink colours under the antialiased contour before warping.
    for ink in [lash,closed]:
        indices=distance_transform_edt(ink[:,:,3]<250,return_distances=False,return_indices=True)
        ink[:,:,:3]=ink[indices[0],indices[1],:3]
    upper, lower = curves(eye['White'][:, :, 3])
    return {'parts': eye, 'lash': lash, 'crease': crease, 'closed': closed,
            'lt': lt, 'lb': lb, 'ct': ct, 'cb': cb, 'upper': upper, 'lower': lower,
            'registration': {'original_lash_x': [int(ox[0]+box[0]), int(ox[-1]+box[0])],
                             'generated_lash_x': [int(cx[0]+box[0]), int(cx[-1]+box[0])]}}


def keyform(eye, openness):
    if openness == 1:
        return {k: v.copy() for k, v in eye['parts'].items()}
    p = openness
    h, w = eye['closed'].shape[:2]
    yy = np.broadcast_to(np.arange(h)[:, None], (h, w)).astype('float32')
    # Match the two eyelash envelopes before interpolation, avoiding two
    # spatially separated outlines. This is a material study, not mesh binding.
    top = eye['lt']*p + eye['ct']*(1-p)
    bottom = eye['lb']*p + eye['cb']*(1-p)
    phase = (yy-top) / np.maximum(bottom-top, 1)
    a = remap_rgba(eye['lash'], eye['lt'] + phase*(eye['lb']-eye['lt']))
    b = remap_rgba(eye['closed'], eye['ct'] + phase*(eye['cb']-eye['ct']))
    upper_lash = morph_lashes(a, b, p)
    # Keep a single crease; the generated plate's additional crease is omitted.
    crease = remap_rgba(eye['crease'], yy-18*(1-p))
    upper_image = Image.fromarray(upper_lash)
    upper_image.alpha_composite(Image.fromarray(crease))
    upper_edge = eye['upper']*p + eye['cb']*(1-p)
    lower_edge = eye['lower']*p + eye['cb']*(1-p)
    aperture = np.minimum(np.clip(yy-upper_edge+.5, 0, 1), np.clip(lower_edge-yy+.5, 0, 1))
    if p == 0:
        aperture[:] = 0
    white = eye['parts']['White'].copy()
    white[:, :, 3] = np.rint(white[:, :, 3]*aperture)
    # Lower lashes move toward the same closing edge, with their line merging
    # into the upper lash rather than remaining as a second closed-eye line.
    low = remap_rgba(eye['parts']['LowerLid'], eye['lower']+(yy-lower_edge)/max(p,.02))
    if p == 0:low[:]=0
    return {'White': white, 'Iris': eye['parts']['Iris'].copy(),
            'UpperLid': np.array(upper_image), 'LowerLid': low}


def refine_hair_edges(parts, blank):
    """Trim one captured lash nub and rejoin a tiny original fringe gap."""
    box=(743,730,766,793);x,y,r,b=box
    layer=parts['Bang_L'].copy();patch=np.array(layer.crop(box))
    xx=np.arange(x,r)[None,:];yy=np.arange(y,b)
    boundary=np.interp(yy,[730,750,775,789,793],[757,753,750,750,747])[:,None]
    keep=np.clip(boundary-xx+.5,0,1)
    fade=np.minimum(np.clip((yy-y)/8,0,1),np.clip((b-1-yy)/8,0,1))[:,None]
    patch[:,:,3]=np.rint(patch[:,:,3]*(1-fade+fade*keep))
    layer.paste(Image.fromarray(patch),(x,y));parts['Bang_L']=layer
    mother=Image.open(ROOT/'reference_v34/rurino_head_master_v34.png').convert('RGBA')
    tipbox=(1112,791,1128,816);tx,ty,tr,tb=tipbox
    hi=Image.new('L',((tr-tx)*4,(tb-ty)*4))
    ImageDraw.Draw(hi).polygon([((px-tx)*4,(py-ty)*4) for px,py in
        [(1125,791),(1127,791),(1116,813),(1115,814),(1121,800)]],fill=255)
    alpha=hi.resize((tr-tx,tb-ty),Image.Resampling.LANCZOS)
    patch=np.array(mother.crop(tipbox));patch[:,:,3]=np.array(alpha)
    layer=parts['Bang_R'].copy();layer.alpha_composite(Image.fromarray(patch),(tx,ty));parts['Bang_R']=layer
    for n in ['Bang_L','Bang_R']:parts[n].save(OUT/'layers'/f'{n}.png')
    return [{'layer':'Bang_L','box':list(box)},{'layer':'Bang_R','box':list(tipbox)}]


def main():
    for folder in ['qa', 'layers', 'keyforms']:
        (OUT/folder).mkdir(parents=True, exist_ok=True)
    manifest = json.loads((SRC/'manifest.json').read_text())
    parts = {v['name']: Image.open(SRC/v['file']).convert('RGBA') for v in manifest['layers']}
    closed_source = Image.open(OUT/'sources/closed-eyes-source.png').convert('RGBA')
    blank = Image.open(SRC/'sources/featureless-skin.png').convert('RGBA')
    edge_patches=refine_hair_edges(parts,blank)
    eyes = {s: prepare_eye(s, parts, closed_source, blank) for s in 'LR'}
    base = Image.new('RGBA', SIZE)
    for n in BASE: base.alpha_composite(parts[n])
    front = [n for n in parts if n not in BASE and not n.startswith(('Eye_', 'Mouth_', 'Brow_'))]
    front += ['Brow_L', 'Brow_R']

    def render(p):
        result = base.copy(); poses = {}
        for side in 'LR':
            pose = keyform(eyes[side], p); poses[side] = pose
            a = pose['Iris']; eye = pose['White'].copy(); f = a[:, :, 3:4].astype('float32')/255
            eye[:, :, :3] = np.rint(a[:, :, :3]*f + eye[:, :, :3]*(1-f))
            xy = BOXES[side][:2]
            result.alpha_composite(Image.fromarray(eye), xy)
            for name in ['UpperLid', 'LowerLid']:
                result.alpha_composite(Image.fromarray(pose[name]), xy)
        result.alpha_composite(parts['Mouth_Neutral'])
        for n in front: result.alpha_composite(parts[n])
        return result, poses

    report = {'scope': 'raster blink material study; no Cubism export','hair_edge_patches':edge_patches,
              'registration': {s: eyes[s]['registration'] for s in 'LR'}, 'poses': []}
    neutral = np.array(render(1)[0])
    prior=np.array(Image.open(SRC/'qa/neutral.png'))
    edge_region=np.zeros(SIZE,bool)
    for patch in edge_patches:
        x,y,r,b=patch['box'];edge_region[y:b,x:r]=True
    assert np.array_equal(neutral[~edge_region],prior[~edge_region])
    report['neutral_changed_only_in_hair_edge_patches']=True
    allowed = np.zeros(SIZE, bool)
    for x,y,r,b in BOXES.values(): allowed[y:b,x:r] = True
    grid = Image.new('RGB', (1800, 230), (225,229,237)); draw = ImageDraw.Draw(grid)
    form_layers = {}
    for index,p in enumerate([1, .75, .5, .25, 0]):
        rendered, poses = render(p); a = np.array(rendered)
        outside = int(np.abs(a.astype('int16')-neutral.astype('int16'))[~allowed].max())
        assert outside == 0
        assert np.array_equal(a[:, :, 3], neutral[:, :, 3])
        if p == 1: assert np.array_equal(a, neutral)
        report['poses'].append({'openness': p, 'outside_eye_boxes_max_change': outside,
                                'visible_aperture_alpha_sum': {s: int(v['White'][:, :, 3].sum()) for s,v in poses.items()},
                                'iris_texture_unchanged': all(np.array_equal(v['Iris'],eyes[s]['parts']['Iris']) for s,v in poses.items())})
        if p == 0:
            assert all(not np.any(v['White'][:, :, 3]) and not np.any(v['LowerLid'][:, :, 3]) for v in poses.values())
        rendered.save(OUT/'keyforms'/f'eye-open-{p:.2f}.png')
        tile = thumbnail(rendered.crop((570,650,1470,1020)), (360,170), (225,229,237))
        grid.paste(tile,(index*360,50)); draw.text((index*360+20,20),f'Eye openness {p:.2f}',fill=(40,45,60))
        if p in [1,.5,0]:
            label={1:'Open',.5:'Half',0:'Closed'}[p]
            form_layers[label]={}
            for side, pose in poses.items():
                for suffix, arr in pose.items():
                    if p == 0 and suffix in ['White','Iris','LowerLid']: continue
                    full = Image.new('RGBA', SIZE); full.paste(Image.fromarray(arr), BOXES[side][:2])
                    name=f'Eye_{side}_{suffix}_{label}'; full.save(OUT/'layers'/f'{name}.png')
                    form_layers[label][name]=full
    grid.save(OUT/'qa/blink-keyforms.jpg',quality=96)
    # Several held-open frames around a fast close and a slower reopening.
    sequence=[1]*24+[.85,.5,.15,0,0,.15,.4,.7,.9]+[1]*21
    frames=[]
    for p in sequence:
        im,_=render(p)
        tile=thumbnail(im.crop((380,180,1660,1400)),(640,640),(225,229,237))
        ImageDraw.Draw(tile).text((12,10),'BLINK MATERIAL STUDY / NOT A CUBISM RIG',fill=(40,45,60))
        frames.append(tile)
    path=OUT/'qa/blink-material-check.png'
    frames[0].save(path,save_all=True,append_images=frames[1:],duration=50,loop=0,disposal=0,blend=0)
    # APNG may coalesce repeated held frames; compare their decoded durations.
    with Image.open(path) as anim:
        expanded=[]
        for i in range(anim.n_frames):
            anim.seek(i); expanded += [np.array(anim.convert('RGB'))]*round(anim.info['duration']/50)
    assert np.array_equal(np.stack(expanded),np.stack([np.array(f) for f in frames]))
    report['apng_lossless']=True
    psd=PSDImage.new('RGBA',SIZE,color=0)
    def group(name,items,visible=True):
        g=Group.new(name,parent=psd);g.visible=visible
        for n,im in items.items():
            box=im.getbbox()
            if not box:continue
            layer=PixelLayer.frompil(im.crop(box),psd_file=psd,layer_name=n,top=box[1],left=box[0]);g.append(layer)
            if '_Iris_' in n:layer.clipping_layer=True
        return g
    group('01_Body_and_Skin',{n:parts[n] for n in BASE})
    group('02_Eyes_Open_DEFAULT',form_layers['Open'])
    group('03_Eyes_Half_ENABLE_ONLY_ONE_EYE_GROUP',form_layers['Half'],False)
    group('04_Eyes_Closed_ENABLE_ONLY_ONE_EYE_GROUP',form_layers['Closed'],False)
    group('05_Neutral_Mouth',{'Mouth_Neutral':parts['Mouth_Neutral']})
    group('06_Foreground_Hair_and_Brows',{n:parts[n] for n in front})
    path=OUT/'Rurino_Head_Blink_Materials_v034.psd';psd.save(path)
    del psd;gc.collect()
    psd=PSDImage.open(path)
    checks=[]
    for label,value in [('Open',1),('Half',.5),('Closed',0)]:
        for g in psd:
            if '_Eyes_' in g.name:g.visible=f'_Eyes_{label}_' in g.name
        actual=np.array(psd.composite(force=True));expected=np.array(Image.open(OUT/'keyforms'/f'eye-open-{value:.2f}.png'))
        err=np.abs(actual.astype('int16')-expected.astype('int16'))
        rgb_error=int(err[:,:,:3][expected[:,:,3]>0].max())
        checks.append({'form':label,'max_visible_rgb_error':rgb_error,'max_alpha_error':int(err[:,:,3].max())})
        edge_pixels=int(np.count_nonzero((err[:,:,:3].max(2)>7)&(expected[:,:,3]>0)))
        checks[-1]['visible_pixels_rgb_error_above_7']=edge_pixels
        assert rgb_error<=12 and edge_pixels<=4 and err[:,:,3].max()<=1, checks
        Image.fromarray(actual).save(OUT/'qa'/f'psd-{label.lower()}.png')
    report['saved_psd_checks']=checks
    report['psd_sha256']=hashlib.sha256(path.read_bytes()).hexdigest()
    report['remaining']=['small eye/hair matte edges still need manual cleanup',
                         'intermediate contours need visual review before mesh keyforms',
                         'no Cubism mesh, parameters, motions or Windows export']
    (OUT/'qa/checks.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':main()
