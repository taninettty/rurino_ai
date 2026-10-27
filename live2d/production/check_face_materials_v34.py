"""Verify the saved PSD, including actual PSD clipping after iris translation."""
import json,hashlib
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
from psd_tools import PSDImage
from split_head_v34 import OUT as BASE,thumbnail
P=BASE/'face_features';Q=P/'qa'
psd=PSDImage.open(P/'Rurino_Head_Facial_Materials_v034.psd')
def walk(group):
    for layer in group:
        if layer.is_group():yield from walk(layer)
        else:yield layer
leaves=list(walk(psd));layers={l.name:l for l in leaves}
assert len(layers)==29 and len(leaves)==29
baseline=np.array(psd.composite(force=True));prior=np.array(Image.open(BASE/'brow_refinement/qa/neutral.png'))
Image.fromarray(baseline).save(Q/'psd-reopened.png')
ap=np.maximum.reduce([np.array(Image.open(P/'masks'/f'Eye_{s}_Opening.png')) for s in ['L','R']])
coordinates={n:layers[n].offset for n in ['Eye_L_Iris','Eye_R_Iris']}
for n in coordinates:assert layers[n].clipping_layer
poses=[(-12,0),(0,0),(12,0),(0,-8),(0,8)];tests=[]
font_path=next((p for p in [Path('/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'),Path('C:/Windows/Fonts/msyh.ttc')] if p.exists()),None)
font=ImageFont.truetype(str(font_path),22) if font_path else ImageFont.load_default()
canvas=Image.new('RGB',(450*len(poses),540),(225,229,237));draw=ImageDraw.Draw(canvas)
labels=['向左看','中性','向右看','向上看','向下看']
for i,(dx,dy) in enumerate(poses):
    for n,(x,y) in coordinates.items():layers[n].offset=(x+dx,y+dy)
    current=np.array(psd.composite(force=True));delta=np.abs(current.astype('int16')-baseline.astype('int16'))
    outside=int(delta[ap==0].max());alpha=int(delta[:,:,3].max())
    assert outside==0,(dx,dy,outside)
    assert alpha==0,(dx,dy,alpha)
    tests.append({'iris_shift_original_px':[dx,dy],'outside_eye_openings_max_change':outside,'alpha_change_max':alpha,'changed_rgb_pixels':int(np.count_nonzero(np.any(delta[:,:,:3]>0,axis=2)))})
    tile=thumbnail(Image.fromarray(current).crop((460,570,1580,1210)),(450,460),(225,229,237));canvas.paste(tile,(i*450,50));draw.text((i*450+20,12),labels[i]+' · PSD 分层检查',font=font,fill=(45,50,65))
canvas.save(Q/'psd-gaze-verification.jpg',quality=95)
for n,offset in coordinates.items():layers[n].offset=offset
landmarks=[]
a=cv2.cvtColor(prior,cv2.COLOR_RGBA2GRAY);b=cv2.cvtColor(baseline,cv2.COLOR_RGBA2GRAY)
for name,(x,y,r,d) in [('left_pupil',(792,822,845,880)),('right_pupil',(1196,822,1250,879)),('mouth',(936,1086,1108,1115))]:
    v=cv2.matchTemplate(b[y-6:d+6,x-6:r+6],a[y:d,x:r],cv2.TM_CCOEFF_NORMED);_,score,_,pos=cv2.minMaxLoc(v);offset=[pos[0]-6,pos[1]-6]
    assert offset==[0,0] and score>.99,(name,offset,score)
    landmarks.append({'feature':name,'best_offset_px':offset,'correlation':score})
assert np.array_equal(baseline[:,:,3]>127,prior[:,:,3]>127)
hidden=np.array(Image.open(Q/'features-hidden.png')).astype('int16');ghosts=[]
for name,(x,y,r,b) in [('left_iris_area',(770,800,890,900)),('right_iris_area',(1150,800,1270,900))]:
    crop=hidden[y:b,x:r];count=int(np.count_nonzero((crop[:,:,2]>crop[:,:,0]+12)&(crop[:,:,3]>200)))
    assert count==0,(name,count)
    ghosts.append({'region':name,'remaining_blue_eye_pixels':count})
report={'saved_psd_layer_count':len(layers),'iris_clipping_flags_preserved':True,'psd_gaze_checks':tests,'neutral_landmarks':landmarks,'neutral_silhouette_unchanged':True,'hidden_layer_ghost_checks':ghosts,'limits':'Tests cover material separation, fixed aperture clipping and neutral alignment. No blink, talking, head turn, Cubism mesh or Windows host verification.'}
(Q/'saved-psd-checks.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
