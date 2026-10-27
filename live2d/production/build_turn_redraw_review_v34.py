"""Inspect independently redrawn turn references; never warp or animate a face."""
import hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'rebuild_v3_4/turn_redraw'

def main():
    (OUT/'qa').mkdir(parents=True,exist_ok=True)
    inputs=[('LEFT / redrawn v2',OUT/'sources/turn-left-v2-source.png'),
            ('FRONT / identity reference',ROOT/'reference_v34/rurino_head_master_v34.png'),
            ('RIGHT / independently redrawn',OUT/'sources/turn-right-source.png')]
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
    report={'method':'two independently generated LibTV viewpoints; no face warp, mirror or interpolated animation',
            'selected_outputs':records,'status':'viewpoint drawing references; not split or rigged',
            'display_only':{'common_crop':[180,0,1868,1540],'uniform_thumbnail_max_size':[600,620]},
            'review':{'left_v1':'superseded: larger apparent turn and unwanted head roll',
                      'left_v2':'more level eye line; new near ear, far eye and jaw drawing',
                      'right':'new near ear, far eye and jaw drawing; asymmetric bangs retained'},
            'remaining':['precise head scale and neck/body registration',
                         'per-part side-view separation and concealed-area painting',
                         'Cubism parameter meshes and changing occlusion validation'],
            'rejected_method':'earlier shared-coordinate head warp withdrawn at user request'}
    (OUT/'selection.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'outputs':len(records)-1,'source_files_verified':True,'source_geometry_modified':False},indent=2))

if __name__=='__main__':main()
