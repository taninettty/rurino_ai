"""Narrow the face artwork while retaining feature layers and PSD layer identity.
Requires the archived t044 PSD; reimport and rig correction are separate steps.
"""
from pathlib import Path
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer
from PIL import Image
import json
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'rebuild_v3_3';OUT.mkdir(exist_ok=True)
psd=PSDImage.open(ROOT/'rebuild_v3_2/Rurino_Frontal_Mouth_t044.psd')
for old in list(psd.descendants()):
 if old.is_group() or old.name!='D_FACE_00':continue
 im=Image.new('RGBA',psd.size);im.alpha_composite(old.topil(),(old.left,old.top))
 # Width only: keep the mouth-to-chin height until turn tracking is corrected.
 im=im.transform(psd.size,Image.Transform.AFFINE,(1/.94,0,768*(1-1/.94),0,1,0),Image.Resampling.BICUBIC)
 box=im.getbbox();new=PixelLayer.frompil(im.crop(box),psd_file=psd,layer_name=old.name,top=box[1],left=box[0]);new._record.tagged_blocks=old._record.tagged_blocks
 parent=old.parent;i=parent.index(old);parent.remove(old);parent.insert(i,new)
 im.save(OUT/'Face_Narrowed.png')
psd.save(OUT/'Rurino_Coordinated_Face_t051.psd')
(OUT/'face-repair.json').write_text(json.dumps({'source':'v0.3.2 candidate t044','face_material_width_scale':.94,'center_highres_x':768,'features_unchanged':True,'rig_status':'pending'},indent=2))
print('Saved t051: face width 94%, all other source layers preserved')
