"""Rebuild right cheek review silhouette; retain original PSD sources untouched.
Reference colors are taken only inside traced hair. No head or face warp.
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
SOURCE=TURN/'right_cheek_ownership/Rurino_Right_Cheek_Ownership_v034.psd'
REFERENCE=TURN/'right_cheek_ownership/qa/saved-psd-open.png'
OUT=TURN/'right_cheek_contour_rework'
def preview(before,after):
 font=ImageFont.truetype(FONT,22)
 sheet=Image.new('RGB',(920,1100),'#e8edf3');d=ImageDraw.Draw(sheet)
 for i,(title,v) in enumerate([('上一版：缺口、三角残线、根部台阶',before),('重修：连续轮廓检查稿',after)]):
  im=Image.fromarray(v).crop((1020,100,1450,1300));im.thumbnail((440,1000));bg=checker((440,1000));bg.paste(im,((440-im.width)//2,0),im);sheet.paste(bg,(i*460+10,60));d.text((i*460+10,20),title,font=font,fill='#26394c')
 sheet.save(OUT/'qa/right-cheek-contour-rework.jpg',quality=97)
 sheet=Image.new('RGB',(1360,790),'#e8edf3');d=ImageDraw.Draw(sheet)
 for i,(title,v,bgcolor) in enumerate([('旧稿：浅底',before,'#faf6ee'),('重修：浅底',after,'#faf6ee'),('重修：深底',after,'#263042')]):
  im=Image.fromarray(v).crop((1080,920,1375,1290)).resize((430,540));bg=Image.new('RGB',im.size,bgcolor);bg.paste(im,(0,0),im);sheet.paste(bg,(i*450+10,55));d.text((i*450+10,16),title,font=font,fill='#26394c')
 for i,(title,v) in enumerate([('旧发根',before),('重修发根',after)]):
  im=Image.fromarray(v).crop((1290,370,1385,495)).resize((120,158));bg=checker(im.size);bg.paste(im,(0,0),im);sheet.paste(bg,(i*450+165,615));d.text((i*450+10,650),title,font=font,fill='#26394c')
 d.text((930,650),'实际透明发片对照',font=font,fill='#26394c');d.text((930,690),'尚未做动作验收',font=font,fill='#26394c')
 sheet.save(OUT/'qa/right-cheek-edge-detail.jpg',quality=97)
def prepare(source):
 ls={l.name:l for l in pixels(source)}
 a=full(ls['Cheek_R_OwnershipClean_LOCAL_REVIEW']);head=np.array(Image.open(REFERENCE).convert('RGBA'))
 before=a.copy();yy,xx=np.indices(a.shape[:2]);rows=np.arange(2048)
 def cv(y,x):return PchipInterpolator(y,x,extrapolate=False)(rows)[:,None]
 # Complete main silhouette, following the dark line of the reference artwork.
 ys=[750,775,800,810,825,850,875,900,925,950,975,980,1000,1025,1050,1075,1100,1125,1150,1175,1185,1200,1220,1240,1250,1260,1270,1273]
 xl=[1252,1246,1236,1231,1223,1219,1213,1205,1198,1186,1214,1212,1208,1202,1196,1190,1183,1176,1167,1157,1152,1147,1137,1126,1120,1113,1105,1102]
 # Use a continuous main inner edge above fork; the small fork supplies the left edge.
 xl[:11]=[1252,1246,1236,1231,1225,1223,1220,1219,1218,1215,1214]
 xr=[1388,1386,1383,1382,1380,1376,1372,1367,1361,1354,1348,1346,1339,1329,1319,1307,1295,1276,1256,1230,1219,1205,1180,1152,1139,1123,1107,1102]
 left=cv(ys,[v-1.6 for v in xl]);right=cv(ys,[v-1 if y<1240 else v for y,v in zip(ys,xr)])
 coverage=np.clip(np.minimum(xx-left+0.5,right-xx+0.5),0,1);coverage=np.nan_to_num(coverage)
 # Original pointed side fork; no neck/skin triangular sliver below it.
 fy=[750,775,800,810,825,850,875,900,925,950,975,1000,1025,1040,1050,1060]
 fl=[1252,1246,1236,1231,1225,1219,1213,1205,1198,1186,1176,1162,1145,1133,1124,1114]
 fr=[1280,1270,1260,1250,1250,1250,1250,1250,1250,1240,1217,1190,1160,1142,1128,1114]
 fc=np.nan_to_num(np.clip(np.minimum(xx-cv(fy,[v-1 for v in fl])+0.5,cv(fy,fr)-xx+0.5),0,1));coverage=np.maximum(coverage,fc)
 # Only reference pixels inside the traced strand may provide color. Repair
 # source transparency holes from the nearest interior hair pixel, not skin.
 inside=coverage>0;valid=(coverage>.99)&(head[:,:,3]>220)
 invalid=inside&~valid
 indices=distance_transform_edt(~valid,return_distances=False,return_indices=True)
 rgb=head[:,:,:3].copy();rgb[invalid]=rgb[indices[0][invalid],indices[1][invalid]]
 new=a.copy();region=(yy>=750);new[region]=0
 new[inside,:3]=rgb[inside];new[inside,3]=np.rint(coverage[inside]*253).astype('uint8')
 # Blend replacement into undamaged upper material over 12 px, keeping its alpha.
 t=(np.clip((yy-750)/12,0,1))[:,:,None];blend=np.rint(a*(1-t)+new*t).astype('uint8');new[(yy>=750)&(yy<762)]=blend[(yy>=750)&(yy<762)]
 # Remove the old rectangular root extension along a smooth taper inside the
 # existing concealed-root material. No face/whole-head warp is involved.
 ry=[350,375,400,425,450,475,500,525,550,580,620,680,740,800,810]
 rx=[1328,1335,1340,1344,1348,1355,1364,1371,1379,1382,1384,1389,1388,1383,1382]
 rootcov=np.nan_to_num(np.clip(cv(ry,rx)-xx+0.5,0,1),nan=1)
 rootregion=(yy>=350)&(yy<810)
 new[rootregion,3]=np.minimum(new[:,:,3],np.rint(rootcov*253).astype('uint8'))[rootregion]
 new[new[:,:,3]==0]=0
 # Drop detached subpixel specks; they are not separate strands.
 components,count=label(new[:,:,3]>0,structure=np.ones((3,3)));sizes=np.bincount(components.ravel());sizes[0]=0
 keep=int(sizes.argmax());new[(components!=0)&(components!=keep)]=0
 for name,v in [('Cheek_R_previous_REVIEW',before),('Cheek_R_ContinuousContour_LOCAL_REVIEW',new)]:Image.fromarray(v).save(OUT/'layers'/(name+'.png'))
 Image.fromarray(np.rint(coverage*255).astype('uint8')).save(OUT/'masks/lower_silhouette.png')
 Image.fromarray(np.rint(rootcov*255).astype('uint8')).save(OUT/'masks/root_taper.png')
 changed=np.any(new!=before,axis=2)
 report={'changed_review_pixels':int(changed.sum()),'added_alpha_pixels':int(((before[:,:,3]==0)&(new[:,:,3]>0)).sum()),'removed_alpha_pixels':int(((before[:,:,3]>0)&(new[:,:,3]==0)).sum()),'edge_or_source_gap_pixels_colored_from_nearest_hair_interior':int(invalid.sum()),'reference_composite_sha256':sha(REFERENCE),'root_original_rgb_preserved_where_retained':bool(np.array_equal(new[(yy<750)&(new[:,:,3]>0),:3],before[(yy<750)&(new[:,:,3]>0),:3]))}
 solid=new[:,:,3]>127;_,count=label(solid,structure=np.ones((3,3)));holes=int((binary_fill_holes(solid)&~solid).sum())
 report['opaque_components']=count;report['enclosed_alpha_holes']=holes
 assert count==1 and holes==0
 preview(before,new)
 return new,report

def main(prepare_only=False):
 for name in ['layers','masks','qa']:(OUT/name).mkdir(parents=True,exist_ok=True)
 source=PSDImage.open(SOURCE);material,records=prepare(source)
 if prepare_only:print(json.dumps(records,indent=2));return
 original={l.name:l for l in pixels(source)};psd=PSDImage.new('RGBA',(2048,2048),color=0);clone(source,psd,psd,[])
 review=Group.new('13_RightCheek_ContinuousContour_REVIEW_OFF',parent=psd);review.visible=False
 name='Cheek_R_ContinuousContour_LOCAL_REVIEW';add(psd,review,Image.fromarray(material),name)
 path=OUT/'Rurino_Right_Cheek_Contour_Rework_v034.psd';psd.save(path);saved=PSDImage.open(path);layers={l.name:l for l in pixels(saved)}
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
 report={'input_psd_sha256':sha(SOURCE),'saved_psd_sha256':sha(path),'pixel_layers':len(layers),'all_131_original_pixel_layers_and_properties_preserved':True,'new_layer_matches_png_after_save':True,'records':records,'states':states,'review_group_default_visible':False,'method':'continuous traced silhouette; source hair colors within mask; nearest interior hair colors for partial edges and source gaps; root alpha taper; detached specks removed','limitations':['current left-view review material only; no new angle artwork','root overlap and moving silhouette require later assembly tests','not a fully repainted hidden surface or a new runtime model','no Cubism mesh, keyforms, body motion or hair physics added'],'libtv_generation_used':False}
 (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--prepare-only',action='store_true');main(p.parse_args().prepare_only)
