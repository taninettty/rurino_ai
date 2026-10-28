"""Repair the left fringe/cheek ownership seam using actual original hair pixels.
Default z-order stays intact; continuous materials and a small underlap are review-only.
"""
import argparse,json
import cv2,numpy as np
from scipy.interpolate import PchipInterpolator
from PIL import Image,ImageDraw,ImageFont
from psd_tools import PSDImage
from psd_tools.api.layers import Group
from complete_hair_backplates_v34 import combine
from complete_fringe_materials_v34 import checker,FONT
from split_left_head_parts_v34 import TURN,pixels,clone,add,sha
from build_hair_flow_redraw_v34 import full
SOURCE=TURN/'crown_root_completion/Rurino_Crown_Roots_v034.psd'
OUT=TURN/'left_fringe_cheek_refinement'
FRINGE_Y=[610,620,630,640,650,660,670,680,690,700,710,720,730,740,750,760,770,780,801]
FRINGE_X=[550,550,551,553,555,558,561,565,569,573,579,584,591,598,610,623,638,655,660]
CHEEK_Y=[610,620,640,660,680,700,710,718,725,740,760,780,801]
CHEEK_X=[550,550,553,558,565,573,579,586,589,588,588,590,593]

def save(n,a,folder='layers'):Image.fromarray(a).save(OUT/folder/(n+'.png'))
def cut(a,m):b=a.copy();b[~m]=0;return b

def prepare(source):
 ls={l.name:l for l in pixels(source)};f=full(ls['Fringe_L_SourceRestored_WHOLE']);c=full(ls['CheekLock_ImageLeft']);o=full(ls['Foreground_Hair_Overlap']);yy,xx=np.indices((2048,2048))
 border=PchipInterpolator(FRINGE_Y,FRINGE_X,extrapolate=False)(np.arange(2048))
 cheek_border=PchipInterpolator(CHEEK_Y,CHEEK_X,extrapolate=False)(np.arange(2048))
 moved=(xx<border[:,None])&(yy>=610)&(yy<=801)
 cheek_select=moved&(xx<cheek_border[:,None]);skin_select=moved&~cheek_select
 fringe=cut(f,~moved);junction=cut(f,cheek_select);skin=cut(f,skin_select)
 assert np.array_equal(combine(combine(fringe,junction),skin),f)
 # These separators run through the empty gap between existing overlay pieces.
 # No eye-state art is copied; only the dedicated foreground hair layer is used.
 left=xx<800;cheek_overlay=left&((xx<600)|(yy>=790));fringe_overlay=left&~cheek_overlay
 oc=cut(o,cheek_overlay);of=cut(o,fringe_overlay);other=cut(o,~left)
 assert np.array_equal(combine(combine(oc,of),other),o)
 pieces={'Fringe_L_ContourCorrected_SOURCE':fringe,'Cheek_L_UpperJunction_SOURCE':junction,'Left_FringeCheek_SkinContext_SOURCE':skin,'Left_Cheek_EyeOverlap_SOURCE':oc,'Left_Fringe_EyeOverlap_SOURCE':of,'Other_Hair_EyeOverlap_SOURCE':other}
 visible_fringe=combine(fringe,of);visible_cheek=combine(combine(c,junction),oc)
 crown=full(ls['CrownFringe_Continuous_Completed_LOCAL_REVIEW']);crown[moved]=0;crown=combine(crown,of)
 complete_cheek=combine(combine(full(ls['Cheek_L_FullMaterial_LOCAL_REVIEW']),junction),oc)
 # Limited overlap along the upper shared edge, hidden beneath the fringe.
 # This is local reconstruction from the same cheek's colour, not a new strand.
 valid=(visible_cheek[:,:,3]>=250)&(visible_cheek[:,:,:3].mean(2)>145)
 w=cv2.GaussianBlur(valid.astype('float32'),(0,0),12)
 colour=np.stack([cv2.GaussianBlur(visible_cheek[:,:,k].astype('float32')*valid,(0,0),12)/np.maximum(w,1e-6) for k in range(3)],2)
 t=np.clip(1-((yy-680)/45)**2,0,1);distance=xx-np.nan_to_num(cheek_border,nan=-10000)[:,None]
 support=(distance>=0)&(distance<=14*t)&(w>.005)&(visible_cheek[:,:,3]<250)&(f[:,:,3]>=250)
 backing=np.zeros_like(f);backing[support,:3]=np.rint(colour[support]).clip(0,255).astype('uint8');backing[support,3]=255
 complete_cheek=combine(backing,complete_cheek)
 arrays={**pieces,'Fringe_L_visible_complete':visible_fringe,'Cheek_L_visible_connected':visible_cheek,'Cheek_L_concealed_underlap':backing,'Crown_continuous_REVIEW':crown,'Cheek_L_complete_REVIEW':complete_cheek,'Fringe_L_before':f,'Cheek_L_before':c}
 for n,a in arrays.items():save(n,a)
 for n,m in [('Cheek_source_reassignment',cheek_select),('Skin_source_reassignment',skin_select),('Cheek_underlap',support)]:save(n,(m*255).astype('uint8'),'masks')
 font=ImageFont.truetype(FONT,20);sheet=Image.new('RGB',(1600,690),'#e8edf3');d=ImageDraw.Draw(sheet);box=(430,540,830,1120)
 for i,(label,a) in enumerate([('原刘海：混入了贴脸发段',f),('修后刘海：恢复原有发尖',visible_fringe),('原贴脸发：上端横向缺口',c),('修后贴脸发：接回原有发段',visible_cheek)]):
  im=Image.fromarray(a).crop(box);bg=checker(im.size);bg.paste(im,(0,0),im);sheet.paste(bg,(i*400,55));d.text((i*400+8,17),label,font=font,fill='#26394c')
 d.text((12,650),'实际独立透明素材，同视口同尺度。可见连接来自原画，眉毛与眼睛没有并入。',font=font,fill='#52647a');sheet.save(OUT/'qa/left-fringe-cheek-junction.jpg',quality=97)
 sheet=Image.new('RGB',(1440,820),'#e8edf3');d=ImageDraw.Draw(sheet)
 for i,(label,a) in enumerate([('连续头顶 / 刘海检查稿',crown),('接通后的左贴脸发检查稿',complete_cheek),('本轮归回的贴脸原画 + 小补边',combine(backing,junction))]):
  im=Image.fromarray(a).crop((420,75,1380,1310));im.thumbnail((460,700));bg=checker((460,710));bg.paste(im,((460-im.width)//2,(710-im.height)//2),im);sheet.paste(bg,(i*480+10,55));d.text((i*480+10,17),label,font=font,fill='#26394c')
 d.text((12,783),'完整材料默认隐藏；新补边最多 14 像素，尚未通过转头、身体动作或物理检查。',font=font,fill='#52647a');sheet.save(OUT/'qa/left-hair-connected-materials.jpg',quality=96)
 records={'cheek_original_pixels_reassigned':int((junction[:,:,3]>0).sum()),'skin_original_pixels_separated':int((skin[:,:,3]>0).sum()),'fringe_foreground_hair_pixels_recovered':int((of[:,:,3]>0).sum()),'cheek_foreground_hair_pixels_recovered':int((oc[:,:,3]>0).sum()),'new_concealed_underlap_pixels':int(support.sum()),'max_underlap_native_pixels':14,'fringe_boundary_native':{'y':FRINGE_Y,'x':FRINGE_X},'cheek_boundary_native':{'y':CHEEK_Y,'x':CHEEK_X}}
 return pieces,crown,complete_cheek,records

def main(prepare_only=False):
 for n in ['layers','masks','qa']:(OUT/n).mkdir(parents=True,exist_ok=True)
 source=PSDImage.open(SOURCE);pieces,crown,cheek,records=prepare(source)
 if prepare_only:print(json.dumps(records,ensure_ascii=False,indent=2));return
 psd=PSDImage.new('RGBA',(2048,2048),color=0);clone(source,psd,psd,[]);oldlookup={l.name:l for l in pixels(source)};dest={l.name:l for l in pixels(psd)}
 replacements={'Fringe_L_SourceRestored_WHOLE':['Fringe_L_ContourCorrected_SOURCE','Cheek_L_UpperJunction_SOURCE','Left_FringeCheek_SkinContext_SOURCE'],'Foreground_Hair_Overlap':['Left_Cheek_EyeOverlap_SOURCE','Left_Fringe_EyeOverlap_SOURCE','Other_Hair_EyeOverlap_SOURCE']}
 for oldname,names in replacements.items():
  old=dest[oldname];parent=old.parent;idx=list(parent).index(old)
  for name in names:
   new=add(psd,parent,Image.fromarray(pieces[name]),name);parent.remove(new);parent.insert(idx,new);idx+=1
  old.visible=False
 review=Group.new('09_LeftFringeCheek_Connected_REVIEW_OFF',parent=psd);review.visible=False
 for key,arr in [('CrownFringe_ContourCorrected_LOCAL_REVIEW',crown),('Cheek_L_Connected_LOCAL_REVIEW',cheek)]:
  g=Group.new(key+'_OFF',parent=review);g.visible=False;add(psd,g,Image.fromarray(arr),key);pieces[key]=arr
 path=OUT/'Rurino_Left_Fringe_Cheek_v034.psd';psd.save(path);saved=PSDImage.open(path);after={l.name:l for l in pixels(saved)}
 for name,old in oldlookup.items():
  new=after[name];assert old.offset==new.offset and np.array_equal(np.array(old.topil()),np.array(new.topil())),name
  assert (old.opacity,old.blend_mode,old.clipping_layer)==(new.opacity,new.blend_mode,new.clipping_layer),name
  assert new.visible==(False if name in replacements else old.visible),name
 for name,a in pieces.items():assert np.array_equal(full(after[name]),a),name
 states=[]
 for state in ['Open','Half','Closed']:
  for doc in [source,saved]:
   for g in doc:
    if g.name.startswith('02_'):g.visible=g.name=='02_'+state
  before=np.array(source.composite(force=True));actual=np.array(saved.composite(force=True));assert np.array_equal(before,actual),state
  states.append({'state':state,'default_composite_rgba_exact':True,'changed_pixels':0})
  if state=='Open':save('saved-psd-open',actual,'qa')
  print('Verified',state,flush=True)
 report={'input_psd_sha256':sha(SOURCE),'saved_psd_sha256':sha(path),'pixel_layers':len(after),'original_106_pixel_data_offsets_and_blending_preserved':True,'replaced_original_layers_hidden':list(replacements),'new_layers_match_pngs':True,'source_partitions_exact':True,'records':records,'states':states,'connected_materials_default_visible':False,'source_z_order_preserved':True,'limitations':['current left-view only; no mirroring or head warp','some old outer-edge antialias and colour contamination remain','limited underlap is reconstructed and not motion approved','other crown/temple ownership and large ponytail shoulders and canvas-cropped ends remain pending','no new Cubism mesh, parameter binding, physics or runtime export'],'libtv_generation_used':False}
 (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--prepare-only',action='store_true');main(p.parse_args().prepare_only)
