"""Restore the frontal neutral aperture from its own art; no side-view transplant.

Writes a separate, neutral-only PSD. Older expression keyforms are references,
not silently reused after changing the default eye boundary.
"""
import gc
import hashlib
import json
import re
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw
from psd_tools import PSDImage
from psd_tools.api.layers import Group, PixelLayer

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'rebuild_v3_4'
OUT = BASE / 'front_neutral'
SIZE = (2048, 2048)
BOXES = {'L': (640, 690, 970, 955), 'R': (1080, 690, 1410, 955)}
# Full-resolution coordinates, separately traced on the frontal underpaint.
APERTURES = {
    'L': 'M 710 846 C 724 797 758 770 800 771 C 851 767 891 799 919 834 C 907 873 886 900 861 904 C 814 910 764 912 734 896 Q 719 882 710 846 Z',
    'R': 'M 1104 835 C 1139 795 1193 765 1240 768 C 1289 767 1322 802 1335 844 C 1323 879 1302 899 1270 904 Q 1216 908 1174 902 C 1138 892 1118 864 1104 835 Z',
}


def path_alpha(path, box, scale=4):
    tokens = re.findall(r'[MLCQZ]|-?\d+(?:\.\d+)?', path)
    points = []; p = np.zeros(2); i = 0
    while i < len(tokens):
        op = tokens[i]; i += 1
        n = {'M': 2, 'L': 2, 'Q': 4, 'C': 6, 'Z': 0}[op]
        v = np.array([float(x) for x in tokens[i:i+n]]).reshape(-1, 2); i += n
        if op in ('M', 'L'):
            p = v[0]; points.append(p.copy())
        elif op in ('Q', 'C'):
            for t in np.linspace(0, 1, 120)[1:]:
                points.append((1-t)**2*p+2*(1-t)*t*v[0]+t*t*v[1] if op == 'Q'
                              else (1-t)**3*p+3*(1-t)**2*t*v[0]+3*(1-t)*t*t*v[1]+t**3*v[2])
            p = v[-1]
    x, y, r, b = box
    im = Image.new('L', ((r-x)*scale, (b-y)*scale))
    ImageDraw.Draw(im).polygon([((px-x)*scale, (py-y)*scale) for px, py in points], fill=255)
    return np.array(im.resize((r-x, b-y), Image.Resampling.LANCZOS))


def full(im, box):
    result = Image.new('RGBA', SIZE)
    result.paste(Image.fromarray(im), box[:2])
    return result


def main():
    for d in ('layers', 'qa', 'masks'):
        (OUT/d).mkdir(parents=True, exist_ok=True)
    source = BASE/'expression_refinement/Rurino_Head_Expression_Materials_v034.psd'
    psd = PSDImage.open(source)
    before = psd.composite(force=True)
    groups = []
    parts = {}
    for group in psd:
        if not group.visible:
            continue
        names = []
        for layer in group:
            n = layer.name.replace('_Open', '') if group.name.startswith('02_') else layer.name
            im = Image.new('RGBA', SIZE)
            im.paste(layer.topil().convert('RGBA'), (layer.left, layer.top))
            parts[n] = im
            names.append(n)
        groups.append((group.name, names))
    del psd; gc.collect()
    raw_full = Image.open(BASE/'underpaint/skin-underpaint-raw.png').convert('RGBA')
    white_full = Image.open(BASE/'face_features/sources/eye-white-source.png').convert('RGBA')
    blank_full = Image.open(BASE/'face_features/sources/featureless-skin.png').convert('RGBA')
    for side, box in BOXES.items():
        raw = np.array(raw_full.crop(box))
        blank = np.array(blank_full.crop(box))
        a = path_alpha(APERTURES[side], box)
        Image.fromarray(a).save(OUT/'masks'/f'Eye_{side}_Opening.png')
        old_iris = np.array(parts[f'Eye_{side}_Iris'].crop(box))
        # Include the original dark upper iris, previously cropped off by the
        # generated white aperture. No colour correction or resized iris.
        iris_mask = path_alpha({
            'L': 'M 800 770 C 766 783 747 811 748 847 C 749 875 763 897 786 907 Q 825 913 861 905 C 882 889 892 868 892 842 C 890 805 866 777 830 771 Q 815 769 800 770 Z',
            'R': 'M 1240 768 C 1276 781 1295 811 1294 846 C 1293 874 1276 898 1254 908 Q 1215 912 1176 904 C 1159 886 1151 861 1152 836 C 1154 801 1180 778 1210 771 Q 1226 768 1240 768 Z',
        }[side], box)
        iris_mask = np.maximum(iris_mask, old_iris[:, :, 3])
        iris = raw.copy(); iris[:, :, 3] = iris_mask
        # Preserve all original source texels in the visible iris. White fill
        # is used only beneath that independently clipped iris.
        white = raw.copy()
        fill = np.array(white_full.crop(box))
        f = iris_mask[:, :, None].astype('float32')/255
        white[:, :, :3] = np.rint(raw[:, :, :3]*(1-f)+fill[:, :, :3]*f)
        white[:, :, 3] = a
        # Extract lash/crease alpha against the matching featureless skin,
        # limited to the existing eye feature support and the corrected edge.
        old_upper = np.array(parts[f'Eye_{side}_UpperLid'].crop(box))
        old_lower = np.array(parts[f'Eye_{side}_LowerLid'].crop(box))
        old_white = np.array(parts[f'Eye_{side}_White'].crop(box))
        support = np.maximum.reduce([old_upper[:, :, 3], old_lower[:, :, 3], old_white[:, :, 3], a])
        support = cv2.dilate((support > 0).astype('uint8'), np.ones((7, 7), np.uint8))
        darkness = np.clip((blank[:, :, :3].mean(2)-raw[:, :, :3].mean(2))/np.maximum(blank[:, :, :3].mean(2)-60, 1), 0, 1)
        # Opaque ink interiors remain exact source RGB. Only the AA perimeter
        # needs unmatting; this prevents skin-coloured chunks on dark lashes.
        alpha = np.clip(darkness*3, 0, 1)*support*(1-a.astype('float32')/255)
        ink = np.zeros_like(raw)
        ink[:, :, :3] = np.clip(np.rint((raw[:, :, :3]-blank[:, :, :3]*(1-alpha[:, :, None]))/np.maximum(alpha[:, :, None], 1/255)), 0, 255)
        ink[:, :, 3] = np.rint(alpha*255)
        yy = np.arange(box[1], box[3])[:, None]
        upper = ink.copy(); upper[yy.repeat(ink.shape[1], axis=1) >= 884] = 0
        lower = ink.copy(); lower[yy.repeat(ink.shape[1], axis=1) < 884] = 0
        for name, im in [('White', white), ('Iris', iris), ('UpperLid', upper), ('LowerLid', lower)]:
            im[im[:, :, 3] == 0] = 0
            parts[f'Eye_{side}_{name}'] = full(im, box)

    # Restore the real foreground hair at the eye intersections. The previous
    # colour-difference cut removed dark reddish hair ink together with lashes.
    # Trace long edges along the source strands, then resolve a narrow band by
    # source colour. The rectangular boxes only bound computation, not cuts.
    mother = Image.open(ROOT/'reference_v34/rurino_head_master_v34.png').convert('RGBA')
    repairs = [
        ('CheekLock_L', (640, 710, 710, 940), 'M 640 710 L 675 710 C 665 754 661 799 666 846 Q 673 902 687 940 L 640 940 Z'),
        ('CheekLock_R', (1340, 710, 1410, 940), 'M 1365 710 C 1376 751 1380 805 1372 843 L 1369 856 Q 1358 900 1340 940 L 1410 940 L 1410 710 Z'),
        ('Bang_L', (680, 710, 780, 800), 'M 680 710 L 758 710 Q 747 752 750 777 L 755 790 Q 704 746 680 710 Z'),
        ('Bang_R', (1095, 710, 1165, 827), 'M 1133 710 L 1150 710 Q 1138 780 1105 816 Q 1126 770 1133 710 Z'),
        ('Bang_R', (1230, 710, 1310, 793), 'M 1242 710 L 1306 710 Q 1280 755 1251 779 Q 1254 745 1242 710 Z'),
        ('Bang_R', (1290, 710, 1360, 817), 'M 1318 710 L 1349 710 Q 1334 770 1295 805 Q 1315 757 1318 710 Z'),
    ]
    for owner, box, trace in repairs:
        src = np.array(mother.crop(box))
        allowed = cv2.dilate((path_alpha(trace, box)>0).astype('uint8'), np.ones((9,9),np.uint8))>0
        backdrop=np.array(raw_full.crop(box))[:,:,:3].astype('int16')
        rgb=src[:,:,:3].astype('int16')
        pink=(rgb[:,:,0]-rgb[:,:,1]>8)&(rgb[:,:,2]-rgb[:,:,1]>2)
        changed=np.max(np.abs(rgb-backdrop),axis=2)>24
        combined=Image.new('RGBA',(box[2]-box[0],box[3]-box[1]))
        for n in ('Bang_L','Bang_R','CheekLock_L','CheekLock_R'):
            combined.alpha_composite(parts[n].crop(box))
        existing=np.array(combined)[:,:,3]
        nearby=cv2.dilate((existing>127).astype('uint8'),np.ones((13,13),np.uint8))>0
        fill=allowed&pink&changed&nearby&(existing<254)
        patch=src.copy();patch[:,:,3]=fill.astype('uint8')*255;patch[~fill]=0
        layer=parts[owner].copy();layer.alpha_composite(Image.fromarray(patch),box[:2]);parts[owner]=layer

    result = PSDImage.new('RGBA', SIZE, color=0)
    for group_name, names in groups:
        group = Group.new(group_name.replace('02_Eyes_Open_DEFAULT', '02_Eyes_Open'), parent=result)
        for n in names:
            im = parts[n]; box = im.getbbox(); assert box
            layer = PixelLayer.frompil(im.crop(box), psd_file=result, layer_name=n, top=box[1], left=box[0])
            group.append(layer)
            if n.endswith('_Iris'):
                layer.clipping_layer = True
            im.save(OUT/'layers'/f'{n}.png')
    path = OUT/'Rurino_Front_Neutral_v034.psd'
    result.save(path)
    del result; gc.collect()
    saved = PSDImage.open(path)
    after = saved.composite(force=True)
    after.save(OUT/'qa/front-neutral.png')
    before.save(OUT/'qa/front-before.png')
    sheet = Image.new('RGB', (1600, 620), '#e1e5ed'); draw = ImageDraw.Draw(sheet)
    for i, (label, im) in enumerate([('Before / oversized aperture', before), ('After / frontal source boundary', after)]):
        tile = im.crop((600,600,1440,1220)).resize((800,590), Image.Resampling.LANCZOS)
        sheet.paste(tile, (i*800, 30), tile); draw.text((i*800+12, 10), label, fill='#202535')
    sheet.save(OUT/'qa/front-eye-before-after.jpg', quality=96)
    ba, aa = np.array(before), np.array(after)
    region = np.zeros(SIZE, bool)
    for x,y,r,b in BOXES.values(): region[y:b,x:r] = True
    error = np.abs(ba.astype('int16')-aa.astype('int16'))
    report = {'status': 'frontal neutral PSD; not a bound model', 'layer_count': len(parts),
              'source_psd_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'psd_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'outside_eye_boxes_max_change': int(error[~region].max()),
              'eye_centers_shifted': False, 'iris_recoloured': False,
              'limitations': ['neutral material only; blink states must be rebuilt against this aperture',
                             'frontal hair completion and independent contours still pending',
                             'no yaw/pitch, body binding or runtime export in this material script']}
    assert report['outside_eye_boxes_max_change'] <= 1
    (OUT/'qa/checks.json').write_text(json.dumps(report, indent=2)+'\n')
    (OUT/'manifest.json').write_text(json.dumps({'canvas':SIZE,'groups':groups,'layers':[{'name':n,'file':f'layers/{n}.png','clip_to':n.replace('_Iris','_White') if n.endswith('_Iris') else None} for n in parts]}, indent=2)+'\n')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
