"""Repair lower left cheek material using traced original strand contours.
Upper concealed root and all historical source layers are preserved.
"""
import argparse,json
import numpy as np
from scipy.ndimage import distance_transform_edt,label,binary_fill_holes
from scipy.interpolate import PchipInterpolator
from PIL import Image,ImageDraw,ImageFont
from psd_tools import PSDImage
from psd_tools.api.layers import Group
from split_left_head_parts_v34 import TURN,pixels,clone,add,sha
from build_hair_flow_redraw_v34 import full
from complete_fringe_materials_v34 import checker,FONT
SOURCE=TURN/'right_cheek_contour_rework/Rurino_Right_Cheek_Contour_Rework_v034.psd'
REFERENCE=TURN/'right_cheek_ownership/qa/saved-psd-open.png'
OUT=TURN/'left_cheek_lower_contour'
def preview(before,after):
 font=ImageFont.truetype(FONT,20)
 sheet=Image.new('RGB',(1320,820),'#e8edf3');d=ImageDraw.Draw(sheet)
 for i,(title,v,col) in enumerate([('修前：混入后层头发',before,None),('修后：分叉间隙与下端轮廓',after,None),('修后深底检查',after,'#253144')]):
  im=Image.fromarray(v).crop((425,700,775,1300)).resize((420,720));bg=checker(im.size) if col is None else Image.new('RGB',im.size,col);bg.paste(im,(0,0),im);sheet.paste(bg,(i*440+10,55));d.text((i*440+10,16),title,font=font,fill='#26394c')
 sheet.save(OUT/'qa/left-cheek-lower-contour.jpg',quality=97)
 sheet=Image.new('RGB',(940,1080),'#e8edf3');d=ImageDraw.Draw(sheet)
 for i,(title,v) in enumerate([('旧左贴脸发检查稿',before),('下部重修：保留上部原检查稿',after)]):
  im=Image.fromarray(v).crop((410,130,820,1310));im.thumbnail((450,970));bg=checker((450,970));bg.paste(im,((450-im.width)//2,0),im);sheet.paste(bg,(i*470+10,55));d.text((i*470+10,16),title,font=font,fill='#26394c')
 d.text((15,1030),'实际透明发片；上部隐藏面和动作仍需继续检查。',font=font,fill='#52647a');sheet.save(OUT/'qa/left-cheek-full-contour.jpg',quality=97)
def prepare(source):
 ls={l.name:l for l in pixels(source)};a=full(ls['Cheek_L_RootClean_LOCAL_REVIEW']);head=np.array(Image.open(REFERENCE).convert('RGBA'))
 before=a.copy();yy,xx=np.indices(a.shape[:2]);rows=np.arange(2048)
 def cv(y,x):return PchipInterpolator(y,x,extrapolate=False)(rows)[:,None]
 def band(y,l,r):return np.nan_to_num(np.clip(np.minimum(xx-cv(y,l)+.5,cv(y,r)-xx+.5),0,1))
 # Open gap between the narrow outer gold strand and the wider front lock.
 gy=[750,775,800,825,850,875,900,925,950,975,1000,1025,1050,1068]
 gl=[485,480,476,470,465,462,460,459,459,460,464,469,478,492]
 gr=[485,486,487,488,490,493,498,502,507,514,522,530,540,547]
 gap=band(gy,[v+1.5 for v in gl],[v-1.5 for v in gr]);new=a.copy();new[:,:,3]=np.rint(new[:,:,3]*(1-gap)).astype('uint8')
 # The thin outer strand ends near y1068. Trim away back-hair colour outside it.
 ny=[950,975,1000,1025,1050,1068];nl=[443,450,459,468,475,491];nr=[461,462,466,471,480,492]
 narrow=band(ny,nl,nr)
 mainleft=cv(gy,[v-1.5 for v in gr]);region=(yy>=975)&(yy<1040)&(xx<mainleft)
 new[region,3]=np.minimum(new[:,:,3],np.rint(narrow*253).astype('uint8'))[region]
 # Long pink fork and the shorter gold fork follow different original contours.
 ly=[1040,1050,1075,1100,1125,1150,1175,1200,1225,1250,1260,1270,1280,1283]
 ll=[536,540,550,563,578,594,610,631,654,684,698,713,731,735]
 lr=[604,608,614,622,631,642,653,667,682,701,711,722,733,735]
 long=band(ly,[v-1.5 for v in ll],[v+1.5 if y<1280 else v for y,v in zip(ly,lr)])
 sy=[1040,1050,1075,1085,1095];sl=[598,608,639,658,681];sr=[651,656,669,675,681]
 short=band(sy,[v-1 for v in sl],[v+1 if y<1095 else v for y,v in zip(sy,sr)])
 by=[750,775,800,825,850,875,900,925,950,975,1000,1025,1040]
 bl=[485,486,487,488,490,493,498,502,507,514,522,530,536]
 br=[584,585,586,590,596,603,612,621,628,634,639,647,651]
 body=band(by,[v-1.3 for v in bl],[v+1.3 for v in br])
 fy=[875,900,925,950,960,970,977];fl=[580,589,608,628,639,650,657];fr=[603,614,624,637,644,652,657]
 side=band(fy,[v-1 for v in fl],[v+1 if y<977 else v for y,v in zip(fy,fr)])
 cov=np.maximum.reduce([long,short,narrow,body,side])
 inside=(yy>=750)&(cov>0);valid=inside&(cov>.99)&(head[:,:,3]>220)
 idx=distance_transform_edt(~valid,return_distances=False,return_indices=True)
 rgb=head[:,:,:3].copy();bad=inside&~valid;rgb[bad]=rgb[idx[0][bad],idx[1][bad]]
 # Retain the already painted outer strand above950 and the prior upper root.
 region=(yy>=750)&((yy>=950)|(xx>=cv(gy,gl)))
 new[region]=0;new[inside,:3]=rgb[inside];new[inside,3]=np.rint(cov[inside]*253).astype('uint8')
 # Twelve-pixel join into original hidden upper material.
 t=np.clip((yy-750)/12,0,1)[:,:,None];mix=np.rint(before*(1-t)+new*t).astype('uint8');seam=(yy>=750)&(yy<762);new[seam]=mix[seam]
 new[new[:,:,3]==0]=0
 components,count=label(new[:,:,3]>0,structure=np.ones((3,3)));sizes=np.bincount(components.ravel());sizes[0]=0
 # Preserve upper historical material exactly; remove only lower isolated specks.
 keep=int(sizes.argmax());new[(yy>=750)&(components!=0)&(components!=keep)]=0
 for name,v in [('Cheek_L_previous_REVIEW',before),('Cheek_L_LowerContour_LOCAL_REVIEW',new)]:Image.fromarray(v).save(OUT/'layers'/(name+'.png'))
 for name,v in [('rear_gap',gap),('lower_hair_silhouette',cov)]:Image.fromarray(np.rint(v*255).astype('uint8')).save(OUT/'masks'/(name+'.png'))
 solid=new[:,:,3]>127;_,count=label(solid,structure=np.ones((3,3)));holes=int((binary_fill_holes(solid)&~solid).sum())
 report={'changed_review_pixels':int(np.any(new!=before,axis=2).sum()),'added_alpha_pixels':int(((before[:,:,3]==0)&(new[:,:,3]>0)).sum()),'removed_alpha_pixels':int(((before[:,:,3]>0)&(new[:,:,3]==0)).sum()),'edge_or_source_gap_pixels_colored_from_nearest_hair_interior':int(bad.sum()),'reference_composite_sha256':sha(REFERENCE),'upper_material_y_below_750_exact':bool(np.array_equal(new[:750],before[:750])),'opaque_components':count,'enclosed_alpha_holes':holes}
 report['repaired_lower_region_enclosed_alpha_holes']=int(((binary_fill_holes(solid)&~solid)&(yy>=750)).sum())
 assert report['upper_material_y_below_750_exact'] and report['repaired_lower_region_enclosed_alpha_holes']==0 and count==1
 preview(before,new)
 return new,report

def main(prepare_only=False):
 for name in ['layers','masks','qa']:(OUT/name).mkdir(parents=True,exist_ok=True)
 source=PSDImage.open(SOURCE);material,records=prepare(source)
 if prepare_only:print(json.dumps(records,indent=2));return
 original={l.name:l for l in pixels(source)};psd=PSDImage.new('RGBA',(2048,2048),color=0);clone(source,psd,psd,[])
 review=Group.new('14_LeftCheek_LowerContour_REVIEW_OFF',parent=psd);review.visible=False
 name='Cheek_L_LowerContour_LOCAL_REVIEW';add(psd,review,Image.fromarray(material),name)
 path=OUT/'Rurino_Left_Cheek_Lower_Contour_v034.psd';psd.save(path);saved=PSDImage.open(path);layers={l.name:l for l in pixels(saved)}
 for oldname,old in original.items():
  new=layers[oldname]
  assert old.offset==new.offset and np.array_equal(np.array(old.topil()),np.array(new.topil())),oldname
  assert (old.opacity,old.blend_mode,old.visible,old.clipping_layer)==(new.opacity,new.blend_mode,new.visible,new.clipping_layer),oldname
 assert np.array_equal(full(layers[name]),material)
 states=[]
 for state in ['Open','Half','Closed']:
  for doc in [source,saved]:
   for g in doc:
    if g.name.startswith('02_'):g.visible=g.name=='02_'+state
  a=np.array(source.composite(force=True));b=np.array(saved.composite(force=True));assert np.array_equal(a,b),state
  states.append({'state':state,'default_composite_changed_pixels':0});print('Verified',state,flush=True)
 report={'input_psd_sha256':sha(SOURCE),'saved_psd_sha256':sha(path),'pixel_layers':len(layers),'all_132_original_pixel_layers_and_properties_preserved':True,'new_layer_matches_png_after_save':True,'records':records,'states':states,'review_group_default_visible':False,'method':'trace left front strand branches; open gap previously occupied by rear hair; remove lower rear overlap; restore lower hair colors within contours; preserve upper material exactly','limitations':['current left-view review material only; no new angle artwork','upper y<750 concealed root/junction remains from earlier candidate and needs further repair','not a fully repainted hidden surface or a new runtime model','no Cubism mesh, keyforms, body motion or hair physics added'],'libtv_generation_used':False}
 (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--prepare-only',action='store_true');main(p.parse_args().prepare_only)
