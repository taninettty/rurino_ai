"""Reopen left-head split and compare all saved blink states to the source PSD."""
import json,hashlib
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from psd_tools import PSDImage
from split_left_head_parts_v34 import ROOT,OUT,SOURCE,pixels,sha

def full_layer(l,size):
 im=Image.new('RGBA',size);im.paste(l.topil().convert('RGBA'),l.offset);return np.array(im)
def main():
 manifest=json.loads((OUT/'manifest.json').read_text());src=PSDImage.open(SOURCE);dest=OUT/'Rurino_Left_Head_Visible_Parts_v034.psd';psd=PSDImage.open(dest)
 source={l.name:l for l in pixels(src)};layers=list(pixels(psd));lookup={l.name:l for l in layers}
 assert len(layers)==len(lookup)==manifest['pixel_layer_count'];assert sum(l.clipping_layer for l in layers)==4
 assert sha(SOURCE)==manifest['source_sha256'];assert sha(dest)==manifest['psd_sha256']
 context=full_layer(source['Context_Skin_Reference'],psd.size);recon=np.zeros_like(context);owners=np.zeros(context.shape[:2],dtype='uint8')
 for item in manifest['parts']:
  l=lookup[item['name']];p=full_layer(l,psd.size);png=np.array(Image.open(OUT/item['file']).convert('RGBA'));assert np.array_equal(p[:,:,3],png[:,:,3]),item['name'];assert np.array_equal(p[png[:,:,3]>0],png[png[:,:,3]>0]),item['name']
  visible=p[:,:,3]>0;recon[visible]=p[visible];owners[visible]+=1
 assert np.all(owners[context[:,:,3]>0]==1);assert not owners[context[:,:,3]==0].any()
 assert np.array_equal(recon[context[:,:,3]>0],context[context[:,:,3]>0])
 for item in manifest['preserved_eye_and_overlap_layers']:
  a=source[item['name']];b=lookup[item['name']];assert a.offset==b.offset and a.visible==b.visible and a.opacity==b.opacity and a.blend_mode==b.blend_mode and a.clipping_layer==b.clipping_layer
  assert np.array_equal(np.array(a.topil()),np.array(b.topil())),item['name']
 for p in [src,psd]:assert [g.name for g in p if g.name.startswith('02_') and g.visible]==['02_Open']
 sheet=Image.new('RGB',(1536,640),'#e9edf4');d=ImageDraw.Draw(sheet);font=ImageFont.truetype('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',22);checks=[]
 for i,state in enumerate(['Open','Half','Closed']):
  for p in [src,psd]:
   for g in p:
    if g.name.startswith('02_'):g.visible=g.name=='02_'+state
  a=np.array(src.composite(force=True));b=np.array(psd.composite(force=True));delta=np.abs(a.astype('int16')-b.astype('int16'));visible=(a[:,:,3]>0)|(b[:,:,3]>0)
  assert delta[:,:,3].max()==0,(state,'alpha',delta[:,:,3].max());assert delta[:,:,:3][visible].max()<=1,(state,'rgb',delta[:,:,:3][visible].max())
  Image.fromarray(b).save(OUT/'qa'/f'saved-psd-{state.lower()}.png')
  tile=Image.fromarray(b).crop((180,0,1700,1660));tile.thumbnail((510,580));sheet.paste(tile,(i*512+(512-tile.width)//2,45),tile);d.text((i*512+12,10),{'Open':'睁眼','Half':'部分闭眼','Closed':'闭眼'}[state]+' · 保存后的 PSD',font=font,fill='#26354a')
  checks.append({'state':state,'source_vs_split_alpha_max_error':int(delta[:,:,3].max()),'source_vs_split_visible_rgb_max_error':int(delta[:,:,:3][visible].max())})
 sheet.save(OUT/'qa/left-head-saved-psd-check.jpg',quality=95)
 review=next(p for p in manifest['parts'] if p['name']=='Boundary_Review_NOT_RIG_READY')
 report={'pixel_layers':len(layers),'clipping_layers':4,'preserved_eye_foreground_layers':len(manifest['preserved_eye_and_overlap_layers']),'preserved_rgba_offsets_visibility_opacity_blend_clipping_exact':True,'all_visible_context_pixels_have_exactly_one_owner':True,'saved_context_visible_rgba_and_full_alpha_exact':True,'saved_psd_states':checks,'boundary_review_pixels':review['visible_pixels'],'source_psd_sha256':sha(SOURCE),'saved_psd_sha256':sha(dest),'limits':['pixel reconstruction does not certify semantic cut boundaries','eyebrows cross hair and skin; nose/mouth not separate yet','concealed roots and skin candidates not adopted','not Cubism meshes or continuous animation']}
 (OUT/'qa/saved-psd-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
