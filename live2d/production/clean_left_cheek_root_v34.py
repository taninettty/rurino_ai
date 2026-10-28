"""Separate confirmed flower remnants from left cheek hair, retaining source pixels.
Only the hidden complete-material candidate receives local replacement hair paint.
"""
import argparse,json
import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import gaussian_filter1d
from PIL import Image,ImageDraw,ImageFont
from psd_tools import PSDImage
from psd_tools.api.layers import Group
from split_left_head_parts_v34 import TURN,pixels,clone,add,sha
from build_hair_flow_redraw_v34 import full
from complete_hair_backplates_v34 import combine
from complete_fringe_materials_v34 import checker,FONT
SOURCE=TURN/'left_fringe_cheek_refinement/Rurino_Left_Fringe_Cheek_v034.psd'
OUT=TURN/'left_cheek_root_cleanup'
EDGE_Y=[235,250,275,295,305,330,350,375,400,425]
EDGE_X=[677,659,637,620,613,594,580,565,550,535]

def save(name,a,folder='layers'):Image.fromarray(a).save(OUT/folder/(name+'.png'))

def prepare(source):
 ls={l.name:l for l in pixels(source)};a=full(ls['CheekLock_ImageLeft']);candidate=full(ls['Cheek_L_Connected_LOCAL_REVIEW']);yy,xx=np.indices((2048,2048))
 centres=PchipInterpolator(EDGE_Y,EDGE_X,extrapolate=False)(np.arange(2048))
 rgb=a[:,:,:3].astype('int16');pink=(rgb[:,:,0]-rgb[:,:,1]>45)&(rgb[:,:,2]-rgb[:,:,1]>15)&(rgb[:,:,0]>145)
 # Trace the hair-side contour; retain the main dark line. Include saturated
 # petal antialias on that line, only inside this confirmed flower junction.
 support=((xx<centres[:,None]-2)|(pink&(xx<centres[:,None]+12)))&(a[:,:,3]>0)&(yy>=235)&(yy<=425)
 context=a.copy();context[~support]=0;clean=a.copy();clean[support]=0
 assert np.array_equal(combine(clean,context),a)
 # Follow the same curved local hair flow, sampling just inside the gold face.
 # A smoothed profile along y avoids copying petal outlines or nearest-edge smears.
 colour=np.zeros((2048,3))
 for y in range(235,426):
  x=int(round(centres[y]));sample=a[y,x+9:x+24];assert np.all(sample[:,3]>=250),(x,y)
  colour[y]=np.median(sample[:,:3],axis=0)
 colour[235:426]=gaussian_filter1d(colour[235:426],3,axis=0)
 fixed=candidate.copy();fixed[support,:3]=np.broadcast_to(colour[:,None,:],(2048,2048,3))[support].round().clip(0,255).astype('uint8')
 repaint=np.zeros_like(a);repaint[support]=fixed[support]
 assert np.array_equal(fixed[~support],candidate[~support])
 assert np.array_equal(fixed[:,:,3],candidate[:,:,3])
 assert not np.any(((fixed[:,:,0].astype('int16')-fixed[:,:,1]>45)&(fixed[:,:,2].astype('int16')-fixed[:,:,1]>15)&(fixed[:,:,0]>145))[support])
 for name,im in [('Cheek_L_before',a),('Cheek_L_FlowerClean_SOURCE',clean),('Cheek_L_FlowerContext_SOURCE',context),('Cheek_L_Connected_before',candidate),('Cheek_L_RootClean_REVIEW',fixed),('Cheek_L_concealed_repaint',repaint)]:save(name,im)
 save('flower_reassignment',(support*255).astype('uint8'),'masks')
 font=ImageFont.truetype(FONT,20);sheet=Image.new('RGB',(1440,610),'#e8edf3');d=ImageDraw.Draw(sheet)
 for i,(label,im) in enumerate([('修前：根部混入花瓣边缘',candidate),('修后：补回金色发面，保留主描边',fixed),('分出的原花瓣残片',context)]):
  im=Image.fromarray(im).crop((480,180,750,470)).resize((459,493));bg=checker(im.size);bg.paste(im,(0,0),im);sheet.paste(bg,(i*480+10,55));d.text((i*480+10,17),label,font=font,fill='#26394c')
 d.text((12,571),'实际透明材料放大对照。补画仅在隐藏检查稿；花瓣原像素独立保留，未删除。',font=font,fill='#52647a');sheet.save(OUT/'qa/left-cheek-root-cleanup.jpg',quality=97)
 sheet=Image.new('RGB',(1000,880),'#e8edf3');d=ImageDraw.Draw(sheet)
 for i,(label,im) in enumerate([('修前完整左贴脸发',candidate),('修后检查稿（默认隐藏）',fixed)]):
  im=Image.fromarray(im).crop((420,130,820,1310));im.thumbnail((470,780));bg=checker((480,780));bg.paste(im,((480-im.width)//2,(780-im.height)//2),im);sheet.paste(bg,(i*500+10,55));d.text((i*500+10,17),label,font=font,fill='#26394c')
 d.text((12,845),'同尺度、同视口；原轮廓 alpha 完全保留。未进行转头或物理验收。',font=font,fill='#52647a');sheet.save(OUT/'qa/left-cheek-full-cleanup.jpg',quality=96)
 return clean,context,fixed,{'reassigned_flower_pixels':int(support.sum()),'candidate_repaint_pixels':int(np.any(fixed!=candidate,axis=2).sum()),'candidate_outside_repair_mask_exact':True,'candidate_alpha_exact':True,'source_partition_exact':True,'native_contour':{'y':EDGE_Y,'x':EDGE_X},'local_rgb_sample_offset_from_contour':[9,24],'sample_smoothing_sigma_y':3}

def main(prepare_only=False):
 for n in ['layers','masks','qa']:(OUT/n).mkdir(parents=True,exist_ok=True)
 source=PSDImage.open(SOURCE);clean,context,fixed,records=prepare(source)
 if prepare_only:print(json.dumps(records,indent=2));return
 lookup={l.name:l for l in pixels(source)};psd=PSDImage.new('RGBA',(2048,2048),color=0);clone(source,psd,psd,[]);dest={l.name:l for l in pixels(psd)}
 old=dest['CheekLock_ImageLeft'];parent=old.parent;idx=list(parent).index(old);expected={}
 for name,a in [('Cheek_L_FlowerClean_SOURCE',clean),('Cheek_L_FlowerContext_SOURCE',context)]:
  new=add(psd,parent,Image.fromarray(a),name);parent.remove(new);parent.insert(idx,new);idx+=1;expected[name]=a
 old.visible=False
 g=Group.new('10_LeftCheek_RootClean_REVIEW_OFF',parent=psd);g.visible=False;name='Cheek_L_RootClean_LOCAL_REVIEW';add(psd,g,Image.fromarray(fixed),name);expected[name]=fixed
 path=OUT/'Rurino_Left_Cheek_RootClean_v034.psd';psd.save(path);saved=PSDImage.open(path);after={l.name:l for l in pixels(saved)}
 for name,old in lookup.items():
  new=after[name];assert old.offset==new.offset and np.array_equal(np.array(old.topil()),np.array(new.topil())),name
  assert (old.opacity,old.blend_mode,old.clipping_layer)==(new.opacity,new.blend_mode,new.clipping_layer),name
  assert new.visible==(False if name=='CheekLock_ImageLeft' else old.visible),name
 for name,a in expected.items():assert np.array_equal(full(after[name]),a),name
 states=[]
 for state in ['Open','Half','Closed']:
  for doc in [source,saved]:
   for g in doc:
    if g.name.startswith('02_'):g.visible=g.name=='02_'+state
  before=np.array(source.composite(force=True));actual=np.array(saved.composite(force=True));assert np.array_equal(before,actual),state
  states.append({'state':state,'default_composite_rgba_exact':True,'changed_pixels':0})
  if state=='Open':save('saved-psd-open',actual,'qa')
  print('Verified',state,flush=True)
 report={'input_psd_sha256':sha(SOURCE),'saved_psd_sha256':sha(path),'pixel_layers':len(after),'original_114_pixel_data_offsets_and_blending_preserved':True,'replaced_original_layer_hidden':'CheekLock_ImageLeft','new_layers_match_pngs':True,'records':records,'states':states,'root_clean_candidate_default_visible':False,'method':'confirmed flower context reassignment; adjacent same-side hair colour continuation within a fixed local mask in hidden candidate only','limitations':['current left-view material only','lower blue patch ownership and old peripheral mixed colour remain to inspect','other roots, right-side fringe tip recovery and large-tail shoulder seams remain pending','off-canvas long-tail tips and motion coverage not completed','no new Cubism mesh, parameter binding, physics or runtime export'],'libtv_generation_used':False}
 (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--prepare-only',action='store_true');main(p.parse_args().prepare_only)
