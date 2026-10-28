"""Integer garment-anchor translation audit; not anatomical head registration."""
import hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from psd_tools import PSDImage
from psd_tools.api.layers import PixelLayer
ROOT=Path(__file__).resolve().parents[1];TURN=ROOT/'rebuild_v3_4/turn_redraw';OUT=TURN/'head_registration'
FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 (OUT/'qa').mkdir(parents=True,exist_ok=True)
 selection=json.loads((TURN/'corner_redraw/selection.json').read_text())['selected'];ims={};records={}
 for name,record in selection.items():
  p=ROOT/record['file'];assert sha(p)==record['sha256'];im=Image.open(p).convert('RGBA');ims[name]=im
  a=np.array(im.resize((1024,1024),Image.Resampling.LANCZOS))[700:810,450:590].astype('int16');r,g,b=a[:,:,:3].transpose(2,0,1)
  yy,xx=np.where((r>1.28*g)&(g<115)&(r>65)&(a[:,:,3]>240));top=int(yy.min());x=int(np.median(xx[yy<=top+2]));anchor=[2*(450+x),2*(700+top)]
  records[name]={'file':record['file'],'source_sha256':sha(p),'garment_apex_native_xy':anchor,'anchor_uncertainty_native_px':6}
 target=np.array(records['front']['garment_apex_native_xy']);psd=PSDImage.new('RGBA',(2176,2176),color=0)
 order=['left-up','up','right-up','left','front','right','left-down','down','right-down'];labels=['左上','抬头','右上','左转','正面','右转','左下','低头','右下']
 sheet=Image.new('RGB',(1536,1698),'#e9edf4');d=ImageDraw.Draw(sheet);font=ImageFont.truetype(FONT,21);small=ImageFont.truetype(FONT,16)
 for i,(name,label) in enumerate(zip(order,labels)):
  offset=64+target-np.array(records[name]['garment_apex_native_xy']);x,y=map(int,offset);assert min(x,y)>=0 and max(x,y)+2048<=2176
  l=PixelLayer.frompil(ims[name],psd_file=psd,layer_name=name,top=y,left=x);psd.append(l);l.visible=name=='front'
  records[name]['canvas_offset_xy']=[x,y];records[name]['translation_from_front_native_xy']=(offset-64).tolist()
  preview=Image.new('RGBA',(2176,2176),'#e9edf4');preview.alpha_composite(ims[name],(x,y));preview=preview.resize((512,512),Image.Resampling.LANCZOS)
  bx=(i%3)*512;by=(i//3)*566;sheet.paste(preview,(bx,by+32));d.text((bx+14,by+4),label,font=font,fill='#26354a')
  ax=bx+(64+int(target[0]))*512/2176;ay=by+32+(64+int(target[1]))*512/2176
  d.line((ax-12,ay,ax+12,ay),fill='#bf3a50',width=2);d.line((ax,ay-12,ax,ay+12),fill='#bf3a50',width=2)
  d.text((bx+12,by+546),'原图平移 '+str(records[name]['translation_from_front_native_xy'])+' px',font=small,fill='#26354a')
 path=OUT/'Rurino_Nine_Direction_Collar_Translation_REFERENCE_v034.psd';psd.save(path)
 saved=PSDImage.open(path);assert len(saved)==9
 for l in saved:
  src=np.array(ims[l.name]);actual=np.array(l.topil().convert('RGBA'));assert actual.shape==src.shape
  assert np.array_equal(actual,src),l.name
  assert list(l.offset)==records[l.name]['canvas_offset_xy'];assert l.visible==(l.name=='front')
 sheet.save(OUT/'qa/nine-direction-collar-alignment.jpg',quality=95)
 report={'scope':'garment neckline apex translation only; not head scale, anatomical neck pivot or rig registration','canvas':[2176,2176],'resampling_of_layers':False,'padding':64,'original_source_rgba_in_saved_psd_exact':True,'sources':records,'psd_sha256':sha(path),'limitations':['anchor measured on 1024 preview; estimated native uncertainty +/- 6 px','collar artwork itself differs; head scale and neck pivot unresolved','nine whole images are reference layers only; do not switch or crossfade them as animation']}
 (OUT/'registration.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps({'saved_psd_verified':True,'anchors':{k:r['translation_from_front_native_xy'] for k,r in records.items()}},indent=2))
if __name__=='__main__':main()
