"""Composite selected local LibTV redraws without anatomical warping.

Selection is explicit in eye_calibration/patch-selection.json. No candidate is
automatically accepted. Masks are polygon interiors with a small inner feather;
all pixels outside each polygon and the full original alpha remain identical.
Crop outputs may use a different pixel resolution. Normalize their resolution
uniformly to the original crop box; never fit, rotate or warp facial landmarks.
"""
import hashlib,json
from pathlib import Path
import cv2
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
TURN=ROOT/'rebuild_v3_4/turn_redraw'
OUT=TURN/'eye_calibration'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    selection=json.loads((OUT/'patch-selection.json').read_text())
    (OUT/'corrected').mkdir(exist_ok=True)
    (OUT/'qa').mkdir(exist_ok=True)
    records=[]
    for side,item in selection['patches'].items():
        source=TURN/item['original'];candidate=OUT/item['candidate']
        assert sha(source)==item['original_sha256']
        assert sha(candidate)==item['candidate_sha256']
        original=np.array(Image.open(source).convert('RGBA'))
        generated_image=Image.open(candidate).convert('RGBA')
        normalization=None
        if 'candidate_crop_xyxy' in item:
            x,y,r,b=item['candidate_crop_xyxy']
            assert 0<=x<r<=2048 and 0<=y<b<=2048
            assert generated_image.width*(b-y)==generated_image.height*(r-x)
            assert list(generated_image.size)==item['candidate_dimensions']
            normalization={'original_output_size':list(generated_image.size),
                           'destination_crop_xyxy':[x,y,r,b],
                           'method':'uniform resolution normalization, LANCZOS; fixed original crop position'}
            generated=original.copy()
            generated[y:b,x:r]=np.array(generated_image.resize((r-x,b-y),Image.Resampling.LANCZOS))
        else:generated=np.array(generated_image)
        assert original.shape==generated.shape==(2048,2048,4)
        polygon=Image.new('L',(2048,2048));ImageDraw.Draw(polygon).polygon(item['polygon'],fill=255)
        inside=np.array(polygon)>0
        if normalization:
            crop_mask=np.zeros(inside.shape,bool);crop_mask[y:b,x:r]=True
            assert not np.any(inside&~crop_mask)
        distance=cv2.distanceTransform(inside.astype('uint8'),cv2.DIST_L2,5)
        mask=np.minimum(distance/item['inner_feather_px'],1)
        # LibTV's nominally opaque face has alpha 252-254. Reject transparent
        # holes but preserve the original alpha byte for every output pixel.
        assert np.all(original[inside,3]>=250) and np.all(generated[inside,3]>=250)
        result=original.copy()
        result[:,:,:3]=np.rint(original[:,:,:3]*(1-mask[:,:,None])+generated[:,:,:3]*mask[:,:,None]).astype('uint8')
        assert np.array_equal(result[~inside],original[~inside])
        assert np.array_equal(result[:,:,3],original[:,:,3])
        for rect in item['protected_rectangles'].values():
            x,y,r,b=rect;assert np.array_equal(result[y:b,x:r],original[y:b,x:r])
        output=OUT/'corrected'/f'turn-{side}-eye-calibrated.png'
        Image.fromarray(result).save(output)
        assert np.array_equal(np.array(Image.open(output).convert('RGBA')),result)
        Image.fromarray(np.rint(mask*255).astype('uint8')).save(OUT/'corrected'/f'{side}-patch-mask.png')
        records.append({'side':side,'output':str(output.relative_to(OUT)),'sha256':sha(output),
                        'changed_pixels':int(np.any(result!=original,axis=2).sum()),
                        'outside_polygon_exact':True,'original_alpha_exact':True,
                        'saved_png_roundtrip_exact':True,
                        'crop_resolution_normalization':normalization,
                        'protected_rectangles_exact':item['protected_rectangles'],
                        'source':item})
    (OUT/'qa/patch-verification.json').write_text(json.dumps({'method':'local RGB compositing; no anatomical warp or mirror; crop outputs use documented uniform pixel-resolution normalization','patches':records},indent=2)+'\n')
    print(json.dumps(records,indent=2))

if __name__=='__main__':main()
