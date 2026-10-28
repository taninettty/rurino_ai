"""Read the saved hair PSD and check lossless recomposition and lock isolation."""
import json
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from psd_tools import PSDImage
from split_left_hair_strands_v34 import SOURCE,OUT,TRACES,FONT,full,dump,sha,pixels

def main():
 man=json.loads((OUT/'manifest.json').read_text());path=OUT/'Rurino_Left_Head_Hair_Strands_v034.psd';src=PSDImage.open(SOURCE);psd=PSDImage.open(path);old={l.name:l for l in pixels(src)};new={l.name:l for l in pixels(psd)}
 assert len(new)==len(list(pixels(psd)))==man['pixel_layer_count']==44
 assert sha(SOURCE)==man['source_sha256'] and sha(path)==man['saved_psd_sha256']
 assert sum(l.clipping_layer for l in new.values())==4
 unchanged=[]
 for name,a in old.items():
  if name in TRACES:continue
  b=new[name];assert a.offset==b.offset and a.visible==b.visible and a.opacity==b.opacity and a.blend_mode==b.blend_mode and a.clipping_layer==b.clipping_layer
  assert np.array_equal(np.array(a.topil()),np.array(b.topil()));unchanged.append(name)
 for parent,traces in TRACES.items():
  a=full(old[parent]);out=np.zeros_like(a);owners=np.zeros(a.shape[:2],dtype='uint8')
  for name in [r[0] for r in traces]+[parent+'_RootBoundary_PENDING']:
   b=full(new[name]);v=b[:,:,3]>0;out[v]=b[v];owners[v]+=1
  assert np.array_equal(out[:,:,3],a[:,:,3]);assert np.array_equal(out[a[:,:,3]>0],a[a[:,:,3]>0]);assert np.all(owners[a[:,:,3]>0]==1)
 checks=[];neutral=None
 for state in ['Open','Half','Closed']:
  for p in [src,psd]:
   for g in p:
    if g.name.startswith('02_'):g.visible=g.name=='02_'+state
  a=np.array(src.composite(force=True));b=np.array(psd.composite(force=True));diff=np.abs(a.astype('int16')-b.astype('int16'));valid=(a[:,:,3]>0)|(b[:,:,3]>0)
  assert diff[:,:,3].max()==0;assert diff[:,:,:3][valid].max()==0
  Image.fromarray(b).save(OUT/'qa'/f'saved-psd-{state.lower()}.png')
  if state=='Open':neutral=b
  checks.append({'state':state,'visible_rgb_max_difference':int(diff[:,:,:3][valid].max()),'alpha_max_difference':int(diff[:,:,3].max())})
 for g in psd:
  if g.name.startswith('02_'):g.visible=g.name=='02_Open'
 isolation=[]
 for row in man['traced_locks']:
  name=row['name'];l=new[name];part=full(l);l.visible=False;image=np.array(psd.composite(force=True));l.visible=True
  changed=np.any(image!=neutral,axis=2);assert changed.any();assert not changed[part[:,:,3]==0].any(),name
  isolation.append({'name':name,'changed_pixels_when_hidden':int(changed.sum()),'outside_lock_changed_pixels':0})
 # Two original parents beside their extracted locks at the same source scale.
 sheet=Image.new('RGB',(1320,900),'#e8edf4');d=ImageDraw.Draw(sheet);font=ImageFont.truetype(FONT,22)
 for i,(parent,box,label) in enumerate([('ShortRearHair_ImageLeft',(180,390,530,1050),'画面左侧'),('ShortRearHair_ImageRight',(1340,390,1910,1050),'画面右侧')]):
  base=Image.fromarray(full(old[parent]));selected=Image.new('RGBA',(2048,2048))
  for row in man['traced_locks']:
   if row['parent']==parent:selected.alpha_composite(Image.fromarray(full(new[row['name']])))
  for j,(title,im) in enumerate([('原大块',base),('本轮独立发束',selected)]):
   tile=im.crop(box);tile.thumbnail((630,370));x=j*660;y=i*450;sheet.paste(tile,(x+(660-tile.width)//2,y+50),tile);d.text((x+18,y+10),label+' · '+title,font=font,fill='#26364b')
 sheet.save(OUT/'qa/coarse-to-strands.jpg',quality=95)
 report={'saved_psd_sha256':sha(path),'source_psd_unchanged':True,'pixel_layers':44,'independent_visible_locks':8,'pending_root_boundary_layers':2,'unaltered_other_layers':len(unchanged),'other_layers_rgba_offsets_flags_exact':True,'source_parent_visible_rgba_and_full_alpha_exact':True,'saved_psd_state_comparison':checks,'isolation_checks':isolation,'scope':'visible segmentation and saved-file integrity; hidden roots, edge matting, movement and Cubism physics not validated'}
 dump(OUT/'qa/saved-psd-verification.json',report);print(json.dumps(report,indent=2))
if __name__=='__main__':main()
