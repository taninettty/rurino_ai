"""Recover cheek hair from face and separate ear/rear context; preserve source slots."""
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
SOURCE=TURN/'right_fringe_tip_recovery/Rurino_Right_Fringe_Tips_v034.psd'
OUT=TURN/'right_cheek_ownership'
Y=[810,825,840,850,875,900,925,950,975,1000,1025,1040,1050,1060]
L=[1230,1224,1221,1218,1212,1204,1197,1185,1175,1161,1144,1132,1123,1114]
R=[1250,1250,1250,1250,1250,1250,1250,1240,1214,1188,1158,1139,1126,1115]
Y2=[975,1000,1025,1050,1075,1100,1125,1150,1175,1200]
X2=[1212,1207,1201,1195,1189,1182,1174,1166,1155,1141]
# Outer edge of the original dark hair stroke, NOT the ear silhouette.
YO=[540,560,580,600,620,640,660,680,700,720,740,760,780,800,820,840,860,880,900,920,940,960,980,1000,1020,1040,1060,1080]
XO=[1380,1380,1381,1382,1383,1385,1387,1389,1389,1389,1388,1387,1385,1383,1381,1377,1374,1371,1367,1362,1357,1350,1346,1339,1332,1323,1315,1303]
REPLACE={
 'FacePaint_AfterRightFringeRecovery_SOURCE':('FacePaint_AfterCheekRecovery_SOURCE','Cheek_R_InnerEdge_FromFace_SOURCE'),
 'Cheek_R_AfterFringeRecovery_SOURCE':('Cheek_R_EarContextRemoved_SOURCE','Cheek_R_EarRearContext_SOURCE')}
def cut(a,m):
 b=a.copy();b[~m]=0;return b
def save(n,a,folder='layers'):Image.fromarray(a).save(OUT/folder/(n+'.png'))
def curve(y,x):return PchipInterpolator(y,x,extrapolate=False)(np.arange(2048))[:,None]
def prepare(source):
 ls={l.name:l for l in pixels(source)};yy,xx=np.indices((2048,2048))
 inner=((xx>=curve(Y,L))&(xx<=curve(Y,R)))|((xx>=curve(Y2,X2))&(xx<1250))
 outer=xx>curve(YO,XO)
 face=full(ls[next(iter(REPLACE))]);cheek=full(ls['Cheek_R_AfterFringeRecovery_SOURCE'])
 pieces={'FacePaint_AfterCheekRecovery_SOURCE':cut(face,~inner),'Cheek_R_InnerEdge_FromFace_SOURCE':cut(face,inner),'Cheek_R_EarContextRemoved_SOURCE':cut(cheek,~outer),'Cheek_R_EarRearContext_SOURCE':cut(cheek,outer)}
 for old,names in REPLACE.items():assert np.array_equal(combine(pieces[names[0]],pieces[names[1]]),full(ls[old])),old
 before=full(ls['Cheek_R_FringeRemoved_LOCAL_REVIEW']);after=combine(cut(before,~outer),pieces['Cheek_R_InnerEdge_FromFace_SOURCE'])
 for n,a in {**pieces,'Cheek_R_before_REVIEW':before,'Cheek_R_OwnershipClean_LOCAL_REVIEW':after}.items():save(n,a)
 save('inner_hair_recovery',(inner*255).astype('uint8'),'masks');save('outer_context_separation',(outer*255).astype('uint8'),'masks')
 font=ImageFont.truetype(FONT,20)
 def preview(filename,items,box,size,footer):
  w,h=size;sheet=Image.new('RGB',(w*len(items),h+100),'#e8edf3');d=ImageDraw.Draw(sheet)
  for i,(label,a) in enumerate(items):
   im=Image.fromarray(a).crop(box);im.thumbnail((w-20,h));bg=checker((w-20,h));bg.paste(im,((w-20-im.width)//2,(h-im.height)//2),im);sheet.paste(bg,(i*w+10,50));d.text((i*w+10,15),label,font=font,fill='#26394c')
  d.text((12,h+65),footer,font=font,fill='#52647a');sheet.save(OUT/'qa'/filename,quality=97)
 preview('right-cheek-ownership-comparison.jpg',[('修前：断边、混入耳朵',before),('修后：恢复内边、移出外侧杂色',after),('移出的耳朵及后层内容',pieces['Cheek_R_EarRearContext_SOURCE'])],(1060,650,1430,1290),(400,640),'实际透明图层，同视口同尺度；移出内容完整保留，未生成新头发。')
 preview('right-cheek-full-material.jpg',[('修前独立贴脸发',before),('修后独立贴脸发（隐藏检查稿）',after)],(1060,380,1450,1300),(440,800),'局部轮廓归属修正；根部、隐藏面与动作仍需检查，尚未绑定。')
 return pieces,after,{'recovered_inner_hair_pixels':int((pieces['Cheek_R_InnerEdge_FromFace_SOURCE'][:,:,3]>0).sum()),'separated_ear_rear_context_pixels':int((pieces['Cheek_R_EarRearContext_SOURCE'][:,:,3]>0).sum()),'source_partitions_exact':True,'outer_boundary_y':YO,'outer_boundary_x':XO,'new_painted_pixels':0}
def main(prepare_only=False):
 for n in ['layers','masks','qa']:(OUT/n).mkdir(parents=True,exist_ok=True)
 source=PSDImage.open(SOURCE);pieces,cheek,records=prepare(source)
 if prepare_only:print(json.dumps(records,indent=2));return
 lookup={l.name:l for l in pixels(source)};psd=PSDImage.new('RGBA',(2048,2048),color=0);clone(source,psd,psd,[]);dest={l.name:l for l in pixels(psd)}
 for oldname,names in REPLACE.items():
  old=dest[oldname];parent=old.parent;idx=list(parent).index(old)
  for name in names:
   new=add(psd,parent,Image.fromarray(pieces[name]),name);new.opacity=old.opacity;new.blend_mode=old.blend_mode;new.visible=old.visible
   parent.remove(new);parent.insert(idx,new);idx+=1
  old.visible=False
 review=Group.new('12_RightCheek_OwnershipClean_REVIEW_OFF',parent=psd);review.visible=False
 name='Cheek_R_OwnershipClean_LOCAL_REVIEW';add(psd,review,Image.fromarray(cheek),name);pieces[name]=cheek
 path=OUT/'Rurino_Right_Cheek_Ownership_v034.psd';psd.save(path);saved=PSDImage.open(path);after={l.name:l for l in pixels(saved)}
 for name,old in lookup.items():
  new=after[name];assert old.offset==new.offset and np.array_equal(np.array(old.topil()),np.array(new.topil())),name
  assert (old.opacity,old.blend_mode,old.clipping_layer)==(new.opacity,new.blend_mode,new.clipping_layer),name
  assert new.visible==(False if name in REPLACE else old.visible),name
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
 report={'input_psd_sha256':sha(SOURCE),'saved_psd_sha256':sha(path),'pixel_layers':len(after),'original_126_pixel_data_offsets_and_blending_preserved':True,'replaced_original_layers_hidden':list(REPLACE),'new_layers_match_pngs':True,'records':records,'states':states,'complete_material_candidates_default_visible':False,'limitations':['conservative inner contour trace; some antialias/skin mixed edge remains','current left-view material only; concealed root and full motion surfaces not completed','ear/rear context retained together; not a completed independent ear','large-tail shoulder junctions and off-canvas tips not completed','no Cubism mesh, parameter keyforms, body motion or physics added'],'libtv_generation_used':False}
 (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--prepare-only',action='store_true');main(p.parse_args().prepare_only)
