"""Verify saved three-view assembly, source preservation and blink guide anchors."""
import gc,json,hashlib
import numpy as np
from PIL import Image,ImageDraw
from psd_tools import PSDImage
from build_eye_registration_v34 import OUT,ROOT,VIEWS,STATES,pixels,sha,sample_blink,font,BOX

def main():
 report=json.loads((OUT/'correspondence.json').read_text());path=OUT/'Rurino_Three_View_Eye_Assembly_v034.psd'
 assert sha(path)==report['psd_sha256']
 psd=PSDImage.open(path);layers=list(pixels(psd));lookup={l.name:l for l in layers}
 assert len(layers)==len(lookup)==119
 assert sum(bool(l.clipping_layer) for l in layers)==26
 assert [g.name for g in psd if g.visible]==['View_Front_SHOW_ONE_VIEW_ONLY']
 for m in report['layer_map']:
  l=lookup[m['target_name']];im=l.topil().convert('RGBA')
  assert list(l.offset)==m['offset'] and list(im.size)==m['dimensions']
  assert hashlib.sha256(im.tobytes()).hexdigest()==m['rgba_sha256'],l.name
  assert bool(l.clipping_layer)==m['clipping'],l.name
 verified={};images={}
 for view,c in VIEWS.items():
  assert sha(c['file'])==report['views'][view]['source_sha256']
  source=PSDImage.open(c['file']);src={l.name:l for l in pixels(source)}
  for m in [m for m in report['layer_map'] if m['view']==view]:
   a=src[m['source_name']];b=lookup[m['target_name']]
   assert a.visible==b.visible and a.opacity==b.opacity and a.clipping_layer==b.clipping_layer
   assert hashlib.sha256(a.topil().convert('RGBA').tobytes()).hexdigest()==m['rgba_sha256']
  del source,src;gc.collect()
  group=next(g for g in psd if g.name=='View_'+view+'_SHOW_ONE_VIEW_ONLY')
  assert [g.name for g in group if g.name.startswith('Blink_') and g.visible]==['Blink_Open']
  for g in psd:g.visible=g==group
  checks=[]
  for state in STATES:
   for g in group:
    if g.name.startswith('Blink_'):g.visible=g.name.split('_')[1]==state
   im=psd.composite(force=True).convert('RGBA');reference=Image.open(OUT/'source-renders'/f'{view.lower()}-{state.lower()}.png').convert('RGBA')
   a=np.array(im).astype('int16');b=np.array(reference).astype('int16');visible=(a[:,:,3]>0)|(b[:,:,3]>0)
   delta=np.abs(a-b);rgb=delta[:,:,:3][visible];mx=int(rgb.max()) if len(rgb) else 0
   assert mx<=1 and int(delta[:,:,3].max())<=1,(view,state,mx)
   checks.append({'state':state,'max_visible_rgb_difference':mx,'max_alpha_difference':int(delta[:,:,3].max())})
   images[view,state]=im
  anchors={}
  for eye,r in report['views'][view]['eyes'].items():
   for state,p in r['blink_guide_anchor_positions'].items():
    sampled=sample_blink(r,p)
    for k in ['upper','lower']:assert np.allclose(sampled[k],r['contours'][state][k]),(view,eye,state,k)
   widths=[]
   for p in np.linspace(0,1,101):
    s=sample_blink(r,p);widths.append(np.array(s['lower'])-s['upper'])
   steps=np.diff(widths,axis=0)
   # A guide must not reopen at a column as the input closes.
   assert float(steps.min())>=-1e-8,(view,eye,'nonmonotone gap',float(steps.min()))
   anchors[eye]={'partial_anchor':r['partial_center_height_ratio'],'samples_checked':101,'min_gap_step':float(steps.min())}
  verified[view]={'source_sha_unchanged':True,'render_checks':checks,'guide_checks':anchors}
 # All crops share identical native coordinates and uniform presentation scale.
 sheet=Image.new('RGB',(1560,840),(237,240,246));d=ImageDraw.Draw(sheet)
 d.text((20,10),'三视角眼部关键形 · 原坐标等比例裁切',font=font(25),fill='#253149')
 for col,view in enumerate(VIEWS):
  d.text((col*520+15,50),{'Left':'朝画面左','Front':'正面','Right':'朝画面右'}[view],font=font(22),fill='#253149')
  for row,state in enumerate(STATES):
   tile=images[view,state].crop(BOX).resize((510,200),Image.Resampling.LANCZOS)
   x=col*520+5;y=110+row*240;sheet.paste(tile,(x,y),tile)
   label={'Open':'睁眼','Partial':'部分闭眼','Closed':'闭眼'}[state]
   if state=='Partial':label+='  开放度 '+ ' / '.join(f'{r["partial_center_height_ratio"]:.2f}' for r in report['views'][view]['eyes'].values())
   d.text((x+8,y-30),label,font=font(18),fill='#253149')
 d.text((15,815),'仅为离散素材检查；开放度为局部导向值，不代表已绑定的连续动画。',font=font(17),fill='#5e6678')
 sheet.save(OUT/'qa/three-view-blink-correspondence.jpg',quality=95)
 overlay=Image.new('RGB',(1560,410),(237,240,246));d=ImageDraw.Draw(overlay)
 d.text((20,10),'眼部对应导线 · 保留各视角原始几何',font=font(25),fill='#253149')
 for col,view in enumerate(VIEWS):
  im=Image.alpha_composite(images[view,'Open'],Image.open(OUT/'guides'/f'{view.lower()}-correspondence.png').convert('RGBA'))
  tile=im.crop(BOX).resize((510,200),Image.Resampling.LANCZOS);overlay.paste(tile,(col*520+5,90),tile)
  pair=report['views'][view]['eye_pair']
  d.text((col*520+15,55),view,font=font(22),fill='#253149')
  d.text((col*520+15,305),f'可见眼白间隔 {pair["visible_aperture_gap_px"]} px',font=font(19),fill='#253149')
 d.text((15,345),'青/橙：画面左/右眼开口；紫：闭合线；红：手工鼻部参考点。',font=font(19),fill='#253149')
 d.text((15,375),'端点是可见眼白边界，非被头发遮住的真实眼角；头部尺度及颈部尚待配准。',font=font(17),fill='#5e6678')
 overlay.save(OUT/'qa/three-view-eye-guides.jpg',quality=95)
 output={'passed':True,'pixel_layers':len(layers),'unchanged_art_layers':len(report['layer_map']),'hidden_guide_layers':3,'clipping_layers':26,'views':verified,'limits':report['limits']}
 (OUT/'qa/saved-assembly-verification.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n');print(json.dumps(output,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
