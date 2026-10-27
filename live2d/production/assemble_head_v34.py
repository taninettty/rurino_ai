"""Add registered concealed plates; test small layer shifts, not Cubism deformation."""
import json,hashlib
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer,Group
from split_head_v34 import OUT,clean_source,thumbnail
W=H=2048

def main():
    a=np.array(Image.open(OUT/'master-cleaned.png'));manifest=json.loads((OUT/'manifest.json').read_text())
    parts={x['name']:Image.open(OUT/x['file']).convert('RGBA') for x in manifest['layers']}
    original_mask=a[:,:,3]>250
    skinraw=Image.open(OUT/'underpaint/skin-underpaint-raw.png').convert('RGBA')
    backraw=Image.open(OUT/'underpaint/backhair-underpaint-raw.png').convert('RGBA')
    back=clean_source(backraw);skin=clean_source(skinraw)
    # Never allow generated plates to enlarge the approved silhouette.
    back[:,:,3]*=original_mask
    head=np.zeros((H,W),bool)
    for name in ['Bang_L','Bang_R','CheekLock_L','CheekLock_R','Face_Reference','Ear_L','Ear_R']:
        head|=np.array(parts[name])[:,:,3]>250
    # Generated features are covered by the original face; facial features are NOT independently rigged yet.
    skin[:,:,3]*=head
    back[back[:,:,3]==0]=0;skin[skin[:,:,3]==0]=0
    supports={'BackHair_Concealed_Support':Image.fromarray(back),'Skin_Concealed_Support':Image.fromarray(skin)}
    for name,im in supports.items():im.save(OUT/'underpaint'/f'{name}.png')
    def render(shifts=None,use_support=True):
        result=Image.new('RGBA',(W,H))
        if use_support:
            for im in supports.values():result.alpha_composite(im)
        for name,im in parts.items():
            dx,dy=(shifts or {}).get(name,(0,0));result.alpha_composite(im,(dx,dy))
        return result
    neutral=render();neutral.save(OUT/'qa/head-with-concealed-plates.png')
    psd=PSDImage.new('RGBA',(W,H),color=0)
    for gname,items in [('01_Concealed_Plates__not_physics_bound',supports),('02_Original_Visible_Cuts',parts)]:
        group=Group.new(gname,parent=psd)
        for name,im in items.items():
            box=im.getbbox();group.append(PixelLayer.frompil(im.crop(box),psd_file=psd,layer_name=name,top=box[1],left=box[0]))
    psd.save(OUT/'Rurino_Head_Material_Working_v034.psd')
    reopened=PSDImage.open(OUT/'Rurino_Head_Material_Working_v034.psd')
    rd=np.array(reopened.composite(force=True));nd=np.array(neutral)
    err=np.abs(rd.astype('int16')-nd.astype('int16'))
    assert err[:,:,3].max()<=1 and err[:,:,:3][nd[:,:,3]>0].max()<=2
    # Registration evidence from independent eyes/mouth/chin patches at 1024 resolution.
    mother=cv2.cvtColor(np.array(Image.open(OUT/'master-cleaned.png').resize((1024,1024))),cv2.COLOR_RGBA2GRAY)
    raw=cv2.cvtColor(np.array(skinraw.resize((1024,1024))),cv2.COLOR_RGBA2GRAY)
    alignment=[]
    for name,box in [('eye_L',(376,392,444,455)),('eye_R',(578,391,644,455)),('mouth',(464,540,555,561)),('chin',(480,608,543,640))]:
        x,y,r,b=box;v=cv2.matchTemplate(raw[y-25:b+25,x-25:r+25],mother[y:b,x:r],cv2.TM_CCOEFF_NORMED);_,score,_,pos=cv2.minMaxLoc(v)
        alignment.append({'patch':name,'score':score,'offset_at_1024':[pos[0]-25,pos[1]-25]})
    interior=cv2.erode(original_mask.astype('uint8'),np.ones((21,21),np.uint8))>0
    cases={'neutral':{},'bangs_out_4px':{'Bang_L':(-8,0),'Bang_R':(8,0)},'cheek_out_4px':{'CheekLock_L':(-8,0),'CheekLock_R':(8,0)},'side_out_4px':{'SideHair_L':(-8,0),'SideHair_R':(8,0)},'flowers_up_3px':{'Flower_L':(0,-6),'Flower_R':(0,-6)}}
    sheet=Image.new('RGB',(600*len(cases),640*2),(35,40,53));draw=ImageDraw.Draw(sheet);tests=[]
    for i,(case,shift) in enumerate(cases.items()):
        record={'case':case,'shifts_in_2048_px':shift}
        for row,supported in enumerate([False,True]):
            im=render(shift,supported);arr=np.array(im);missing=interior&(arr[:,:,3]<220)
            record['interior_gap_pixels_'+('with_support' if supported else 'without_support')]=int(missing.sum())
            crop=im.crop((360,80,1680,1360));tile=thumbnail(crop,(600,600),(42,47,60));sheet.paste(tile,(600*i,640*row+32))
            draw.text((600*i+12,640*row+10),case+(' / concealed plates' if supported else ' / cuts only'),fill='white')
        tests.append(record)
    sheet.save(OUT/'qa/small-shift-diagnostics.jpg',quality=92)
    # Two seconds of a modest material stress test, explicitly not a Live2D preview.
    frames=[]
    for k in range(32):
        t=np.sin(2*np.pi*k/32);d=round(8*t)
        im=render({'Bang_L':(-d,0),'Bang_R':(d,0),'CheekLock_L':(-d,0),'CheekLock_R':(d,0)})
        tile=thumbnail(im.crop((350,70,1700,1390)),(620,620),(226,229,237));ImageDraw.Draw(tile).text((12,10),'MATERIAL SHIFT CHECK - NOT A LIVE2D RIG',fill=(60,60,70));frames.append(tile)
    frames[0].save(OUT/'qa/material-shift-check.gif',save_all=True,append_images=frames[1:],duration=80,loop=0,disposal=2)
    final=thumbnail(neutral,(800,800),(226,229,237));final.save(OUT/'qa/head-progress.jpg',quality=95)
    report={'status':'material working source; NOT RIGGED', 'psd_layer_count':len(parts)+len(supports),'skin_registration':alignment,'neutral_psd_alpha_max_error':int(err[:,:,3].max()),'neutral_psd_rgb_max_error':int(err[:,:,:3][nd[:,:,3]>0].max()),'small_layer_shift_tests':tests,'limits':['visible hair contours need close inspection, especially brow/fringe intersections','shared rear support is provisional; requires splitting and parent mapping before independent tail physics','small translated layers do not validate X/Y head perspective, face shape, blink or mouth rigs','generated support is clipped to the neutral silhouette; large rotations need more hidden-area painting','head/shoulder source is not yet aligned to the existing full-body model']}
    (OUT/'qa/material-checks.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
