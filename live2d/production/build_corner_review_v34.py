"""Audit nine independently drawn direction references without geometric warping."""
import hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];TURN=ROOT/'rebuild_v3_4/turn_redraw';OUT=TURN/'corner_redraw'
NAMES={'left-up':'左上','up':'抬头','right-up':'右上','left':'朝画面左','front':'正面','right':'朝画面右','left-down':'左下','down':'低头','right-down':'右下'}
ORDER=list(NAMES)
FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
def f(size):return ImageFont.truetype(FONT,size)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 inputs={k:OUT/'sources'/f'corner-{k}-source.png' for k in ['left-up','right-up','left-down','right-down']}
 inputs.update({'up':TURN/'pitch_redraw/sources/pitch-up-v2-source.png','down':TURN/'pitch_redraw/sources/pitch-down-source.png','left':TURN/'eye_calibration/corrected/turn-left-eye-calibrated.png','right':TURN/'eye_calibration/corrected/turn-right-eye-calibrated.png','front':ROOT/'reference_v34/rurino_head_master_v34.png'})
 review_file=OUT/'review-input.json';reviews=json.loads(review_file.read_text()) if review_file.exists() else {}
 selection_file=OUT/'selection-input.json'
 if selection_file.exists():
  for key,relative in json.loads(selection_file.read_text())['selected_files'].items():inputs[key]=OUT/relative
 files=[]
 for delivery_path in sorted((OUT/'sources').glob('delivery*.json')):files.extend(json.loads(delivery_path.read_text())['files'])
 assert len({file['resourceId'] for file in files})==len(files)
 verified=[]
 for file in files:
  p=OUT/'sources'/file['filename'];assert p.stat().st_size==file['sizeBytes'];key=file['filename'][7:-11]
  status=json.loads((OUT/'sources'/f'{key}-task-status.json').read_text());assert status['outcome']=='SUCCEEDED' and len(status['artifacts'])==1
  assert status['artifacts'][0]['resource_id']==file['resourceId']
  with Image.open(p) as check:check.verify()
  verified.append({'selected':p in inputs.values(),'file':str(p.relative_to(ROOT)),'task_id':status['task_id'],'resource_id':file['resourceId'],'bytes':p.stat().st_size,'sha256':sha(p),'png_decode_verified':True})
 images={};records={}
 for key,p in inputs.items():
  im=Image.open(p).convert('RGBA');assert im.size==(2048,2048);alpha=np.array(im)[:,:,3];assert (alpha==0).sum()>10000
  images[key]=im;records[key]={'file':str(p.relative_to(ROOT)),'sha256':sha(p),'dimensions':list(im.size),'zero_alpha_pixels':int((alpha==0).sum()),'review':reviews.get(key,'pending visual review')}
 previous=json.loads((TURN/'pitch_redraw/selection.json').read_text())['selected']
 for key in ['up','down','left','right','front']:assert records[key]['sha256']==previous[key.title()]['sha256'],key
 assert len({r['sha256'] for r in records.values()})==9
 crop=(180,0,1868,1540)
 sheet=Image.new('RGB',(1800,1860),(234,238,245));d=ImageDraw.Draw(sheet)
 d.text((20,14),'九方向转头结构参考 · 原坐标等比例对照',font=f(31),fill='#253149')
 for i,key in enumerate(ORDER):
  col=i%3;row=i//3;x=col*600;y=65+row*570
  d.rounded_rectangle((x+6,y+6,x+594,y+564),12,fill='#fafbfd',outline='#a5b1c4',width=2)
  tile=images[key].crop(crop);tile.thumbnail((570,510));sheet.paste(tile,(x+(600-tile.width)//2,y+48),tile)
  label=NAMES[key]+(' · 本轮新增' if '-' in key else ' · 已有参考')
  d.text((x+20,y+10),label,font=f(24),fill='#253149')
 d.text((20,1790),'九张绘画参考已收集；头部尺度/颈部配准、完整拆层与组合参数绑定尚未完成。',font=f(24),fill='#53617b')
 d.text((20,1828),'这不是九点绑定或连续转头演示；角度提示词未作三维标定。',font=f(22),fill='#53617b')
 sheet.save(OUT/'qa/nine-direction-review.jpg',quality=96)
 detail=Image.new('RGB',(1600,1440),(234,238,245));d=ImageDraw.Draw(detail)
 d.text((20,15),'四角组合视角 · 五官 / 下颌 / 颈部细节',font=f(29),fill='#253149')
 # Identical crop and uniform scale preserve actual eye/jaw spacing in review.
 for i,key in enumerate(['left-up','right-up','left-down','right-down']):
  x=(i%2)*800;y=65+(i//2)*650;tile=images[key].crop((470,500,1560,1460));tile.thumbnail((780,600));detail.paste(tile,(x+(800-tile.width)//2,y+40),tile)
  d.text((x+20,y+5),NAMES[key],font=f(25),fill='#253149')
 d.text((20,1385),'同一裁切和显示比例；可见眼型受俯仰、遮挡和视线共同影响，不能硬套固定眼距比。',font=f(22),fill='#53617b')
 detail.save(OUT/'qa/corner-face-detail.jpg',quality=96)
 revisions=[key for key,p in inputs.items() if '-v2-' in p.name and key in ['left-up','right-up','right-down']]
 if revisions:
  comparison=Image.new('RGB',(600*len(revisions),1090),(234,238,245));dd=ImageDraw.Draw(comparison)
  dd.text((20,12),'组合视角修订对照 · 上：第一版 / 下：选用修订版',font=f(27),fill='#253149')
  for col,key in enumerate(revisions):
   for row,p in enumerate([OUT/'sources'/f'corner-{key}-source.png',inputs[key]]):
    tile=Image.open(p).convert('RGBA').crop(crop);tile.thumbnail((580,470));comparison.paste(tile,(col*600+(600-tile.width)//2,100+row*490),tile)
    dd.text((col*600+20,65+row*490),NAMES[key]+(' · 第一版' if row==0 else ' · 修订版'),font=f(23),fill='#253149')
  dd.text((20,1050),'独立重画，保留原件；轮廓仍待逐部件配准及网格组合检查。',font=f(23),fill='#53617b')
  comparison.save(OUT/'qa/corner-revision-comparison.jpg',quality=96)
 report={'scope':'nine-direction independent drawing review; not a Cubism model','selected':records,'new_corner_count':4,'existing_axis_count':5,'display':{'common_crop':list(crop),'uniform_scale_only':True,'source_geometry_modified':False},'missing_direction_drawings':[],'full_material_separation_complete':False,'neck_registration_complete':False,'continuous_animation_verified':False,'limits':['independent drawings may differ in head scale or neck/collar placement','yaw/pitch prompts are targets, not calibrated 3D angles','source gaze and eyelid openness vary','hidden anatomical eye corners not recovered','cannot switch or crossfade these whole images to claim a Live2D rig']}
 (OUT/'selection.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 (OUT/'qa/source-verification.json').write_text(json.dumps({'passed':True,'generated_downloaded_verified':len(verified),'source_files':verified,'unchanged_existing_sources':{k:r['sha256'] for k,r in records.items() if '-' not in k},'art_review_is_not_runtime_validation':True},ensure_ascii=False,indent=2)+'\n')
 print(json.dumps({'verified_new_files':len(verified),'review_directions':len(records),'geometry_modified':False,'rig_complete':False},indent=2))
if __name__=='__main__':main()
