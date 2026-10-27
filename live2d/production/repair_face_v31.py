"""Repair existing raster layers for PSD re-import; preserve layer names/order.

The PSD alone does not update the rig. Re-import in Cubism and export/inspect it.
Requires archived rebuild_v3/layers PNGs and Rurino_Template_Named.psd beside
the production directory. This records the production edit, not a standalone
converter for arbitrary PSDs or a replacement for the already-updated CMO.
"""
from pathlib import Path
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer

ROOT = Path(__file__).resolve().parents[1]
OLD = ROOT / 'rebuild_v3'
OUT = ROOT / 'rebuild_v3_1'
OUT.mkdir(exist_ok=True)
SIZE = (1536, 2048)

def load(name):
    return Image.open(OLD / 'layers' / (name + '.png')).convert('RGBA')

def shifted(im, dx):
    result = Image.new('RGBA', SIZE)
    result.alpha_composite(im, (dx, 0))
    return result

replacements = {}
# Mirror the existing left half to remove the mouth's asymmetric skin fringe.
interior = load('Mouth_Interior')
left = interior.crop((728, 530, 767, 590))
mouth = Image.new('RGBA', SIZE)
mouth.alpha_composite(left, (729, 530))
mouth.alpha_composite(left.transpose(Image.Transpose.FLIP_LEFT_RIGHT), (768, 530))
a = np.array(mouth)
# Exclude skin-colored pixels around the existing expression's mouth boundary.
keep = ((a[:, :, 1] < 172) & (a[:, :, 0].astype(float)-a[:, :, 1] > 25)).astype('uint8')*255
mask = Image.fromarray(keep).filter(ImageFilter.GaussianBlur(.55))
a[:, :, 3] = (a[:, :, 3].astype(float)*np.array(mask)/255).astype('uint8')
# Compensate the transferred oral-mesh neutral offset measured in SDK output.
replacements['D_MOUTH_00'] = shifted(Image.fromarray(a), 3)

face = load('Face_Base')
yy, xx = np.indices((SIZE[1], SIZE[0]))
for name, semantic in [('D_MOUTH_03', 'Mouth_Upper'), ('D_MOUTH_01', 'Mouth_Lower')]:
    old = load(semantic)
    a = np.array(face)
    alpha = np.array(old)[:, :, 3].astype(float)
    if semantic == 'Mouth_Lower':
        # Jaw contour used to be copied into the bottom corners of this cover.
        alpha *= np.clip((603-yy)/12, 0, 1)
    a[:, :, 3] = alpha.astype('uint8')
    replacements[name] = Image.fromarray(a)

# A centered, symmetric closed lip, confined to the width of the oral cavity.
# Reuse the original line color; render the edited contour at 2x material size.
lip = Image.new('RGBA', (SIZE[0]*2, SIZE[1]*2))
d = ImageDraw.Draw(lip)
points=[]
for t in np.linspace(0, 1, 100):
    x=366+36*t; y=274.5+4*4*t*(1-t)
    points.append((x*4,y*4))
d.line(points, fill=(137,78,72,205), width=4)
lip=lip.resize(SIZE,Image.Resampling.LANCZOS)
replacements['D_MOUTH_01'].alpha_composite(lip)

# Shift every eye component together by two review pixels toward the center.
# Tighten excess sclera without separating the pupil from its lashes.
for side, dx, ids in [
    ('L',4,{'Sclera':'D_EYE_00','Iris':'D_EYE_BALL_00','Upper':'D_EYE_08','Lower':'D_EYE_02'}),
    ('R',-4,{'Sclera':'D_EYE_01','Iris':'D_EYE_BALL_01','Upper':'D_EYE_09','Lower':'D_EYE_03'}),
]:
    for part, ident in ids.items():
        im=load(f'Eye_{side}_{part}')
        if part=='Sclera':
            cx=661 if side=='L' else 865
            im=im.transform(SIZE,Image.Transform.AFFINE,(1/.94,0,cx*(1-1/.94),0,1,0),Image.Resampling.BICUBIC)
        replacements[ident]=shifted(im,dx)

psd=PSDImage.open(OLD/'Rurino_Template_Named.psd')
changed=[]
for old in list(psd.descendants()):
    if old.is_group() or old.name not in replacements: continue
    im=replacements[old.name];box=im.getbbox()
    # Preserve IDs when supplied by the originating PSD.
    new=PixelLayer.frompil(im.crop(box),psd_file=psd,layer_name=old.name,top=box[1],left=box[0])
    new._record.tagged_blocks=old._record.tagged_blocks
    parent=old.parent;index=parent.index(old);parent.remove(old);parent.insert(index,new)
    changed.append(old.name)
psd.save(OUT/'Rurino_Face_Corrected_t032.psd')
psd.composite(force=True).save(OUT/'material-neutral.png')
(OUT/'face-repair.json').write_text(json.dumps({'changed':changed,'review_eye_shift_px':{'left':2,'right':-2},'sclera_width_scale':.94,'note':'Must re-import, verify mapping, and export in Cubism.'},indent=2))
print('Saved repaired PSD:',len(changed),'layers updated')
