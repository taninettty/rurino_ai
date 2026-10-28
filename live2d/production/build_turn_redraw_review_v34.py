"""Inspect independently redrawn turn references; never warp or animate a face."""
import hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'rebuild_v3_4/turn_redraw'

def main():
    (OUT/'qa').mkdir(parents=True,exist_ok=True)
    left=OUT/'eye_calibration/corrected/turn-left-eye-calibrated.png'
    right=OUT/'eye_calibration/corrected/turn-right-eye-calibrated.png'
    inputs=[('LEFT / local eye redraw' if left.exists() else 'LEFT / redrawn v2',left if left.exists() else OUT/'sources/turn-left-v2-source.png'),
            ('FRONT / identity reference',ROOT/'reference_v34/rurino_head_master_v34.png'),
            ('RIGHT / local eye redraw' if right.exists() else 'RIGHT / independently redrawn',right if right.exists() else OUT/'sources/turn-right-source.png')]
    sheet=Image.new('RGB',(1800,680),(225,229,237));draw=ImageDraw.Draw(sheet);records=[]
    for i,(label,path) in enumerate(inputs):
        with Image.open(path) as check:check.verify()
        im=Image.open(path).convert('RGBA');assert im.size==(2048,2048)
        alpha=np.array(im)[:,:,3];assert (alpha==0).sum()>10000
        records.append({'label':label,'file':str(path.relative_to(ROOT)),'bytes':path.stat().st_size,
                        'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'dimensions':list(im.size),
                        'zero_alpha_pixels':int((alpha==0).sum())})
        # Identical crop and uniform display scale only. Source assets unchanged.
        tile=im.crop((180,0,1868,1540));tile.thumbnail((600,620))
        sheet.paste(tile,(i*600+(600-tile.width)//2,50),tile)
        draw.text((i*600+12,15),label,fill=(40,45,60))
    sheet.save(OUT/'qa/turn-redraw-comparison.jpg',quality=96)
    report={'method':'two independently generated LibTV viewpoints, with selected local eye redraw patches; no face warp, mirror or interpolated animation',
            'selected_outputs':records,'status':'viewpoint drawing references; separate side-eye PSDs available; full head not split or rigged',
            'display_only':{'common_crop':[180,0,1868,1540],'uniform_thumbnail_max_size':[600,620]},
            'review':{'left_v1':'superseded: larger apparent turn and unwanted head roll',
                      'left_v2':'more level eye line; new near ear, far eye and jaw drawing',
                      'right':'new near ear, far eye and jaw drawing; asymmetric bangs retained'},
            'remaining':['precise head scale and neck/body registration',
                         'per-part side-view separation and concealed-area painting',
                         'Cubism parameter meshes and changing occlusion validation'],
            'rejected_method':'earlier shared-coordinate head warp withdrawn at user request'}
    report['eye_calibration']={'selection':'eye_calibration/patch-selection.json',
                               'measurements':'eye_calibration/qa/eye-measurements.json',
                               'local_patch_verification':'eye_calibration/qa/patch-verification.json',
                               'limits':'static drawing review only; reference pitch and gaze differ; no fixed eye-gap ratio'}
    report['side_eye_layers']={'status':'separate 10-layer PSD for each side, small gaze material checks only',
                               'details':'eye_layers/STATUS.md','verification':'eye_layers/qa/saved-psd-verification.json'}
    report['side_blink_materials']={'status':'two 20-layer PSDs; open/half/closed material keyforms, not a continuous rig', 'details':'side_blink_refinement/STATUS.md', 'verification':'side_blink_refinement/qa/saved-psd-verification.json'}
    report['eye_correspondence']={'status':'119-layer assembly; source art unchanged; per-eye partial blink guide anchors; not a registered head or rig','details':'eye_registration/STATUS.md','verification':'eye_registration/qa/saved-assembly-verification.json'}
    report['pitch_drawings']={'status':'two selected independent up/down drawings; not split or rigged; four combined corner drawings still missing','details':'pitch_redraw/STATUS.md','selection':'pitch_redraw/selection.json','verification':'pitch_redraw/qa/source-verification.json'}
    report['corner_drawings']={'status':'four selected corner drawings and nine-direction review; head/neck registration, full separation and rigging incomplete','details':'corner_redraw/STATUS.md','selection':'corner_redraw/selection.json','verification':'corner_redraw/qa/source-verification.json'}
    report['left_head_parts']={'status':'36-layer visible ownership draft; 19 original eye/overlap layers exact; boundaries and concealed parts unfinished','details':'left_head_parts/STATUS.md','verification':'left_head_parts/qa/saved-psd-verification.json'}
    report['collar_registration']={'status':'integer garment-anchor translation only; not anatomical registration','details':'head_registration/STATUS.md','verification':'head_registration/registration.json'}
    report['individual_hair_locks']={'status':'eight visible short-hair locks; 44-layer head PSD; hidden roots, remaining hair and physics unfinished','details':'left_hair_strands/STATUS.md','verification':'left_hair_strands/qa/saved-psd-verification.json'}
    (OUT/'selection.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'outputs':len(records)-1,'source_files_verified':True,'source_geometry_modified':False},indent=2))

if __name__=='__main__':main()
