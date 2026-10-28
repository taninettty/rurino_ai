"""Recover right fringe tips from misassigned original parts and foreground hair.
Maintain original display slots; assembled materials remain hidden for review.
"""
import argparse,json
import numpy as np
from scipy.interpolate import PchipInterpolator
from PIL import Image,ImageDraw,ImageFont
from psd_tools import PSDImage
from psd_tools.api.layers import Group
from split_left_head_parts_v34 import TURN,pixels,clone,add,sha
from build_hair_flow_redraw_v34 import full
from complete_hair_backplates_v34 import combine
from complete_fringe_materials_v34 import checker,FONT
SOURCE=TURN/'left_cheek_root_cleanup/Rurino_Left_Cheek_RootClean_v034.psd'
OUT=TURN/'right_fringe_tip_recovery'
YS=[690,710,730,750,775,800,825,835,850,860,875,885,895]
LEFT=[1198,1203,1206,1209,1212,1211,1209,1207,1203,1199,1192,1187,1180]
RIGHT=[1267,1263,1258,1253,1246,1237,1226,1221,1214,1208,1197,1190,1181]
SOURCES={
 'FacePaint_Visible_NOT_FEATURE_SPLIT_BrowRemoved_LOCAL':('FacePaint_AfterRightFringeRecovery_SOURCE','RightFringe_FromFace_SOURCE'),
 'CheekLock_ImageRight':('Cheek_R_AfterFringeRecovery_SOURCE','RightFringe_FromCheek_SOURCE'),
 'Fringe_R_Context_AfterHairlineRecovery':('Fringe_R_Context_AfterTipRecovery_SOURCE','RightFringe_FromContext_SOURCE')}

def save(n,a,folder='layers'):Image.fromarray(a).save(OUT/folder/(n+'.png'))
def cut(a,m):b=a.copy();b[~m]=0;return b

def prepare(source):
 ls={l.name:l for l in pixels(source)};yy,xx=np.indices((2048,2048));left=PchipInterpolator(YS,LEFT,extrapolate=False)(np.arange(2048));right=PchipInterpolator(YS,RIGHT,extrapolate=False)(np.arange(2048));support=(xx>=left[:,None])&(xx<=right[:,None])
 recovered=np.zeros((2048,2048,4),dtype='uint8');pieces={};records=[]
 for name,(remain_name,hair_name) in SOURCES.items():
  original=full(ls[name]);hair=cut(original,support);remain=cut(original,~support);assert np.array_equal(combine(remain,hair),original),name
  pieces[remain_name]=remain;pieces[hair_name]=hair;recovered=combine(recovered,hair)
  records.append({'source_layer':name,'reassigned_hair_pixels':int((hair[:,:,3]>0).sum()),'source_partition_exact':True})
 overlay=full(ls['Other_Hair_EyeOverlap_SOURCE']);pieces['RightFringe_ForegroundTips_SOURCE']=overlay
 # The old overlay feathers into pale skin outside this rightmost lock. Clip
 # only its review copy to the traced hair contour. Preserve the default source.
 trim=(xx>=1180)&(yy>=765)&~support&(overlay[:,:,3]>0)
 overlay_review=overlay.copy();overlay_review[trim]=0
 fringe_before=full(ls['Fringe_R_SourceRestored_WHOLE']);fringe_after=combine(combine(recovered,fringe_before),overlay_review)
 crown_before=full(ls['CrownFringe_ContourCorrected_LOCAL_REVIEW']);crown_after=combine(combine(recovered,crown_before),overlay_review)
 cheek_before=full(ls['Cheek_R_FullMaterial_LOCAL_REVIEW']);cheek_after=cheek_before.copy();cheek_after[support&(full(ls['CheekLock_ImageRight'])[:,:,3]>0)]=0
 arrays={**pieces,'RightFringe_recovered_original':recovered,'RightFringe_overlay_review':overlay_review,'RightFringe_before':fringe_before,'RightFringe_complete_REVIEW':fringe_after,'Crown_continuous_REVIEW':crown_after,'Cheek_R_after_REVIEW':cheek_after}
 for n,a in arrays.items():save(n,a)
 save('rightmost_tip_ownership',(support*255).astype('uint8'),'masks');save('overlay_pale_fringe_trim',(trim*255).astype('uint8'),'masks')
 font=ImageFont.truetype(FONT,20);sheet=Image.new('RGB',(1440,465),'#e8edf3');d=ImageDraw.Draw(sheet)
 for i,(label,a) in enumerate([('修前：右侧细刘海被截短',fringe_before),('修后：接回原发尖，裁去覆盖层白边',fringe_after),('本轮找回的原画（非新生成）',combine(recovered,overlay_review))]):
  im=Image.fromarray(a).crop((940,630,1320,920)).resize((456,348));bg=checker((460,355));bg.paste(im,(2,3),im);sheet.paste(bg,(i*480+10,55));d.text((i*480+10,17),label,font=font,fill='#26394c')
 d.text((12,429),'三列均为真实透明素材，同视口同尺度。中间刘海保持连续，尚未做动作验收。',font=font,fill='#52647a');sheet.save(OUT/'qa/right-fringe-tip-recovery.jpg',quality=97)
 sheet=Image.new('RGB',(1000,800),'#e8edf3');d=ImageDraw.Draw(sheet)
 for i,(label,a) in enumerate([('修前连续头顶 / 刘海',crown_before),('修后完整检查稿（默认隐藏）',crown_after)]):
  im=Image.fromarray(a).crop((500,75,1380,940));im.thumbnail((480,690));bg=checker((480,690));bg.paste(im,((480-im.width)//2,(690-im.height)//2),im);sheet.paste(bg,(i*500+10,55));d.text((i*500+10,17),label,font=font,fill='#26394c')
 d.text((12,757),'保留先前左侧修整；补回右侧原画像素，没有拉伸或镜像头部。',font=font,fill='#52647a');sheet.save(OUT/'qa/crown-right-tip-comparison.jpg',quality=96)
 return pieces,crown_after,cheek_after,{'sources':records,'foreground_hair_pixels':int((overlay[:,:,3]>0).sum()),'review_overlay_trimmed_pixels':int(trim.sum()),'native_tip_bounds':{'y':YS,'left':LEFT,'right':RIGHT},'source_recovery_uses_eye_layers':False,'new_painted_pixels':0}

def main(prepare_only=False):
 for n in ['layers','masks','qa']:(OUT/n).mkdir(parents=True,exist_ok=True)
 source=PSDImage.open(SOURCE);pieces,crown,cheek,records=prepare(source)
 if prepare_only:print(json.dumps(records,indent=2));return
 lookup={l.name:l for l in pixels(source)};psd=PSDImage.new('RGBA',(2048,2048),color=0);clone(source,psd,psd,[]);dest={l.name:l for l in pixels(psd)}
 replace={**SOURCES,'Other_Hair_EyeOverlap_SOURCE':('RightFringe_ForegroundTips_SOURCE',)}
 for oldname,names in replace.items():
  old=dest[oldname];parent=old.parent;idx=list(parent).index(old)
  for name in names:
   new=add(psd,parent,Image.fromarray(pieces[name]),name);parent.remove(new);parent.insert(idx,new);idx+=1
  old.visible=False
 review=Group.new('11_RightFringe_CompleteTips_REVIEW_OFF',parent=psd);review.visible=False
 for name,a in [('CrownFringe_RightTipsRecovered_LOCAL_REVIEW',crown),('Cheek_R_FringeRemoved_LOCAL_REVIEW',cheek)]:
  g=Group.new(name+'_OFF',parent=review);g.visible=False;add(psd,g,Image.fromarray(a),name);pieces[name]=a
 path=OUT/'Rurino_Right_Fringe_Tips_v034.psd';psd.save(path);saved=PSDImage.open(path);after={l.name:l for l in pixels(saved)}
 for name,old in lookup.items():
  new=after[name];assert old.offset==new.offset and np.array_equal(np.array(old.topil()),np.array(new.topil())),name
  assert (old.opacity,old.blend_mode,old.clipping_layer)==(new.opacity,new.blend_mode,new.clipping_layer),name
  assert new.visible==(False if name in replace else old.visible),name
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
 report={'input_psd_sha256':sha(SOURCE),'saved_psd_sha256':sha(path),'pixel_layers':len(after),'original_117_pixel_data_offsets_and_blending_preserved':True,'replaced_original_layers_hidden':list(replace),'new_layers_match_pngs':True,'records':records,'states':states,'complete_material_candidates_default_visible':False,'method':'trace rightmost fringe contour; recover original hair from face, cheek and context; include dedicated foreground hair and trim its pale exterior fringe in review copy','limitations':['current left-view artwork only; no new angle keyforms','minor source antialias and remaining skin/hair mixed edges still require inspection','right cheek and temple full concealed surfaces remain incomplete','large-tail shoulder junctions and off-canvas tips not completed','no Cubism meshes, parameter binding, body motion or physics added'],'libtv_generation_used':False}
 (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--prepare-only',action='store_true');main(p.parse_args().prepare_only)
