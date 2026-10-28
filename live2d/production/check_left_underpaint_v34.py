"""Verify downloaded concealed-paint candidates. Do not auto-adopt generated faces."""
import json,hashlib
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];TURN=ROOT/'rebuild_v3_4/turn_redraw';OUT=TURN/'left_head_parts'
def main():
 records=[];delivery=json.loads((OUT/'sources/delivery.json').read_text());ref=Image.open(TURN/'eye_calibration/corrected/turn-left-eye-calibrated.png').convert('RGBA');base=cv2.cvtColor(np.array(ref.resize((1024,1024))),cv2.COLOR_RGBA2GRAY)
 crops={'far_eye':[306,354,371,440],'near_eye':[477,352,563,440],'nose':[374,445,408,494],'mouth':[387,524,468,548],'chin':[415,601,453,625]}
 sheet=Image.new('RGB',(1500,760),'#e9edf4');d=ImageDraw.Draw(sheet);font=ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',20)
 for i,(label,im) in enumerate([('已确认左转原图',ref)]+[(f['filename'],Image.open(OUT/'sources'/f['filename']).convert('RGBA')) for f in delivery['files']]):
  tile=im.crop((390,80,1560,1340));tile.thumbnail((490,690));sheet.paste(tile,(i*500+(500-tile.width)//2,45),tile);d.text((i*500+12,10),label,font=font,fill='#26354a')
 sheet.save(OUT/'qa/underpaint-candidates-NOT-ADOPTED.jpg',quality=95)
 for f in delivery['files']:
  p=OUT/'sources'/f['filename'];assert p.stat().st_size==f['sizeBytes']
  with Image.open(p) as im:im.verify()
  im=Image.open(p).convert('RGBA');assert im.size==(2048,2048);a=np.array(im);gray=cv2.cvtColor(np.array(im.resize((1024,1024))),cv2.COLOR_RGBA2GRAY);measurements={}
  for name,(x,y,r,b) in crops.items():
   tpl=base[y:b,x:r];pad=25;search=gray[y-pad:b+pad,x-pad:r+pad];result=cv2.matchTemplate(search,tpl,cv2.TM_CCOEFF_NORMED);_,score,_,loc=cv2.minMaxLoc(result)
   measurements[name]={'template_correlation':round(score,4),'best_match_displacement_native_px':[2*(loc[0]-pad),2*(loc[1]-pad)],'interpretation':'appearance match diagnostic, not validated anatomical registration'}
  records.append({'file':f['filename'],'task_id':f['taskId'],'resource_id':f['resourceId'],'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'decoded_dimensions':list(im.size),'zero_alpha_pixels':int((a[:,:,3]==0).sum()),'matches':measurements,'adopted_in_psd':False,'status':'concealed-paint candidate only; isolate local concealed skin/hair patches and verify registration before use'})
 (OUT/'qa/underpaint-verification.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n');print(json.dumps(records,indent=2))
if __name__=='__main__':main()
