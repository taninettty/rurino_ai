"""Review independently drawn pitch anchors; no image warp or animation."""
import hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];TURN=ROOT/'rebuild_v3_4/turn_redraw';OUT=TURN/'pitch_redraw'
FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
def f(s):return ImageFont.truetype(FONT,s)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 selection=json.loads((OUT/'selection-input.json').read_text())
 inputs={'Up':OUT/selection['up'],'Down':OUT/selection['down'],'Front':ROOT/'reference_v34/rurino_head_master_v34.png','Left':TURN/'eye_calibration/corrected/turn-left-eye-calibrated.png','Right':TURN/'eye_calibration/corrected/turn-right-eye-calibrated.png'}
 images={};records={}
 for k,p in inputs.items():
  with Image.open(p) as check:check.verify()
  im=Image.open(p).convert('RGBA');assert im.size==(2048,2048)
  a=np.array(im)[:,:,3];assert (a==0).sum()>10000
  images[k]=im;records[k]={'file':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'sha256':sha(p),'dimensions':list(im.size),'zero_alpha_pixels':int((a==0).sum()),'stage':'independent drawing reference; unrigged'}
 # Same source rectangle and same scale for every view; no registration warp.
 crop=(180,0,1868,1540)
 sheet=Image.new('RGB',(1800,710),(234,238,245));d=ImageDraw.Draw(sheet)
 d.text((18,10),'上下俯仰结构稿 · 低头 / 正面 / 抬头',font=f(30),fill='#253149')
 labels={'Down':'低头｜新增重绘参考','Front':'正面｜已有身份基准','Up':'抬头｜新增重绘参考'}
 for i,k in enumerate(['Down','Front','Up']):
  tile=images[k].crop(crop);tile.thumbnail((590,570));sheet.paste(tile,(i*600+(600-tile.width)//2,100),tile)
  d.text((i*600+20,62),labels[k],font=f(24),fill='#253149')
 d.text((20,672),'独立绘画参考，未拆层/绑定；身体及头部尺度仍待配准，提示词角度不等于实测角度。',font=f(22),fill='#53617b')
 sheet.save(OUT/'qa/pitch-three-view-review.jpg',quality=96)
 compass=Image.new('RGB',(1500,1580),(234,238,245));d=ImageDraw.Draw(compass)
 d.text((20,15),'转头结构覆盖检查｜实线格为已有绘画参考',font=f(30),fill='#253149')
 positions={'Up':(1,0),'Left':(0,1),'Front':(1,1),'Right':(2,1),'Down':(1,2)}
 names={'Up':'抬头','Left':'朝画面左','Front':'正面','Right':'朝画面右','Down':'低头'}
 for k,(col,row) in positions.items():
  x=col*500;y=65+row*480
  d.rounded_rectangle((x+6,y+6,x+494,y+474),12,fill='#f9fafc',outline='#a4afc2',width=2)
  tile=images[k].crop(crop);tile.thumbnail((460,410));compass.paste(tile,(x+(500-tile.width)//2,y+45),tile)
  d.text((x+20,y+10),names[k]+' · 绘画参考',font=f(22),fill='#253149')
 for col,row,label in [(0,0,'左上'),(2,0,'右上'),(0,2,'左下'),(2,2,'右下')]:
  x=col*500;y=65+row*480
  d.rectangle((x+16,y+16,x+484,y+464),outline='#c5ccda',width=2)
  d.text((x+130,y+190),label+'组合关键形',font=f(27),fill='#6d788f')
  d.text((x+182,y+235),'尚未制作',font=f(24),fill='#6d788f')
 d.text((20,1530),'5 个方向的参考图 ≠ 9 点绑定完成；全部连续转头与表情组合仍须验证。',font=f(24),fill='#53617b')
 compass.save(OUT/'qa/head-direction-coverage.jpg',quality=95)
 report={'scope':'pitch drawing references and five-direction coverage review; no new runtime rig','selected':records,'review':selection['review'],'display':{'common_crop':list(crop),'uniform_scale_only':True,'source_pixels_modified':False},'missing_diagonal_drawings':['LeftUp','RightUp','LeftDown','RightDown'],'continuous_motion_verified':False,'required_next':['review identity and compact jaw across all directions','separate face ears bangs rear hair and paint concealed structure','register head/body anchors','draw combined yaw/pitch targets','bind per-part Cubism meshes and check blink/gaze/mouth combinations']}
 (OUT/'selection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'verified_sources':len(records),'source_geometry_modified':False,'rig_complete':False},indent=2))
if __name__=='__main__':main()
