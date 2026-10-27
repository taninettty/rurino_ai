"""Inspect saved side blink PSD keyforms and isolated gaze, not runtime motion."""
import gc,json,hashlib
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from psd_tools import PSDImage
from build_side_blink_materials_v34 import OUT,OLD,TURN,CFG,sha,save_json

def main():
 (OUT/'qa').mkdir(exist_ok=True);records=json.loads((OLD/'source-crops.json').read_text());reports=[]
 sheet=Image.new('RGB',(1536,1230),(225,229,237));draw=ImageDraw.Draw(sheet)
 edge_sheet=Image.new('RGB',(1536,816),(225,229,237));ed=ImageDraw.Draw(edge_sheet)
 for col,(side,record) in enumerate(records.items()):
  dest=OUT/side;box=record['crop_xyxy'];path=dest/f'Rurino_Turn_{side.title()}_Blink_Materials_v034.psd'
  psd=PSDImage.open(path);layers=list({id(l):l for l in psd.descendants() if l.kind=='pixel'}.values());lookup={l.name:l for l in layers}
  assert len(layers)==len(lookup)==20
  assert sum(l.clipping_layer for l in layers)==4
  groups={state:next(g for g in psd if g.name=='02_'+state) for state in ['Open','Half','Closed']}
  assert groups['Open'].visible and not groups['Half'].visible and not groups['Closed'].visible
  def select(state):
   for n,g in groups.items():g.visible=n==state
  checks=[];baseline=None
  protected=np.array(Image.open(dest/'masks/Editable_Region.png'))==0
  for row,state in enumerate(groups):
   select(state);actual=np.array(psd.composite(viewport=tuple(box),force=True))
   if baseline is None:baseline=actual.copy()
   assert np.array_equal(actual[protected],baseline[protected]), 'keyform changed protected face/hair pixels'
   expected=np.array(Image.open(dest/'qa'/f'{state.lower()}-keyform.png').crop(box).convert('RGBA'))
   error=np.abs(actual.astype('int16')-expected.astype('int16'))
   # The PSD clipping renderer and the local flattened preview disagree at
   # a few partially transparent aperture texels. Validate opaque areas
   # separately; deliver the actual reopened PSD rendering as the preview.
   ap=np.maximum.reduce([np.array(Image.open(dest/'layers'/f'{state}_{n}_White.png'))[:,:,3] for n in CFG[side]])
   severe=error[:,:,:3].max(2)>3
   assert error[:,:,:3].max()<=12 and severe.sum()<=20 and error[:,:,3].max()<=1,(side,state,error.max())
   assert not (severe&(ap==255)).any(), 'opaque eye interior differs'
   assert not (severe&(ap==0)).any(), 'difference outside antialiased aperture'
   Image.fromarray(actual).save(dest/'qa'/f'psd-{state.lower()}.png')
   sheet.paste(Image.fromarray(actual),(col*768,row*410+24),Image.fromarray(actual));draw.text((col*768+8,row*410+6),side.upper()+' / '+state.upper()+' - saved PSD keyform',fill=(40,45,60))
   checks.append({'state':state,'psd_vs_local_rgb_max':int(error[:,:,:3].max()),'alpha_max':int(error[:,:,3].max()),'antialiased_pixels_rgb_error_over_3':int(severe.sum()),'protected_pixels_unchanged_between_states':True})
   if state=='Closed':
    edit=np.array(Image.open(dest/'masks/Editable_Region.png'))>128
    hair=np.array(Image.open(dest/'layers/Foreground_Hair_Overlap.png'))[:,:,3]>0
    a=actual.astype('int16');r,g,b=a[:,:,:3].transpose(2,0,1)
    residue=(g-r>12)&(b-r>12)&edit&~hair
    assert residue.sum()==0,(side,int(residue.sum()))
    checks[-1]['cyan_iris_residue_pixels']=int(residue.sum())
  gaze_checks=[]
  for state in ['Open','Half']:
   select(state);baseline=np.array(psd.composite(viewport=tuple(box),force=True))
   irises=[lookup[f'{state}_{n}_Iris'] for n in CFG[side]];offsets={l.name:l.offset for l in irises}
   apertures=[np.array(Image.open(dest/'layers'/f'{state}_{n}_White.png'))[:,:,3] for n in CFG[side]]
   outside=np.maximum.reduce(apertures)==0
   for dx,dy in [(-6,0),(6,0),(0,-4),(0,4)]:
    for l in irises:x,y=offsets[l.name];l.offset=(x+dx,y+dy)
    a=np.array(psd.composite(viewport=tuple(box),force=True))
    assert np.array_equal(a[outside],baseline[outside]),(side,state,dx,dy)
    Image.fromarray(a).save(dest/'qa'/f'psd-{state.lower()}-gaze-{dx}-{dy}.png')
    gaze_checks.append({'state':state,'shift':[dx,dy],'outside_apertures_unchanged':True})
   for l in irises:l.offset=offsets[l.name]
  iris_checks=[]
  for n in CFG[side]:
   a=lookup[f'Open_{n}_Iris'];b=lookup[f'Half_{n}_Iris']
   assert a.offset==b.offset and np.array_equal(np.array(a.topil()),np.array(b.topil()))
   white=np.array(Image.open(dest/'layers'/f'Open_{n}_White.png')).astype('int16');r,g,bl=white[:,:,:3].transpose(2,0,1)
   assert not (((g-r>12)&(bl-r>12))&(white[:,:,3]>240)).any()
   iris_checks.append({'eye':n,'open_half_iris_texture_and_offset_identical':True,'sclera_cyan_residue_pixels':0})
  select('Open');full=np.array(psd.composite(force=True));source=np.array(Image.open(TURN/record['source']).convert('RGBA'))
  outside_band=np.ones(full.shape[:2],bool);x,y,r,b=box;outside_band[y:b,x:r]=False
  context=np.array(Image.open(dest/'layers/Context_Skin_Reference.png').convert('RGBA'))
  assert np.array_equal(context[outside_band],source[outside_band])
  # PSD rendering normalizes hidden RGB at alpha=0 and can round visible RGB
  # by one level. Alpha/geometry and the source-context PNG remain exact.
  delta=np.abs(full.astype('int16')-source.astype('int16'))
  assert delta[:,:,3][outside_band].max()==0
  assert delta[:,:,:3][outside_band&(source[:,:,3]>0)].max()<=1
  # Compare the new PSD with the previously delivered PSD at identical scale.
  old=Image.open(OLD/side/'qa/psd-gaze-1.png').convert('RGBA');new=Image.open(dest/'qa/psd-open.png').convert('RGBA')
  for k,(label,im) in enumerate([('PREVIOUS',old),('CLEANED',new)]):
   edge_sheet.paste(im,(k*768,col*408+24),im);ed.text((k*768+8,col*408+6),side.upper()+' / '+label,fill=(40,45,60))
  reports.append({'side':side,'psd_sha256':sha(path),'pixel_layers':len(layers),'clipping_layers':4,'saved_psd_states':checks,'saved_psd_gaze_checks':gaze_checks,'iris_checks':iris_checks,'outside_eye_band_context_exact_rgba':True,'outside_eye_band_render_alpha_exact':True,'outside_eye_band_render_visible_rgb_max':int(delta[:,:,:3][outside_band&(source[:,:,3]>0)].max()),
  'scope':'three editable material keyforms; not continuous blink, head-turn or Cubism runtime validation'})
  del psd;gc.collect()
 sheet.save(OUT/'qa/side-blink-keyforms.jpg',quality=96);edge_sheet.save(OUT/'qa/side-eye-cleanup-comparison.jpg',quality=96)
 save_json(OUT/'qa/saved-psd-verification.json',reports);print(json.dumps(reports,indent=2))
if __name__=='__main__':main()
