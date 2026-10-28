"""Complete local concealed upper cheek surface from same-strand colour profiles.
This is inferred local repaint in a hidden review candidate, not source recovery.
"""
import argparse,json
import numpy as np
from scipy.ndimage import gaussian_filter1d,label,binary_fill_holes
from scipy.interpolate import PchipInterpolator
from PIL import Image,ImageDraw,ImageFont
from psd_tools import PSDImage
from psd_tools.api.layers import Group
from split_left_head_parts_v34 import TURN,pixels,clone,add,sha
from build_hair_flow_redraw_v34 import full
from complete_fringe_materials_v34 import checker,FONT
SOURCE=TURN/'left_cheek_lower_contour/Rurino_Left_Cheek_Lower_Contour_v034.psd'
OUT=TURN/'left_cheek_upper_surface'
def preview(before,after):
 font=ImageFont.truetype(FONT,20);sheet=Image.new('RGB',(1320,800),'#e8edf3');d=ImageDraw.Draw(sheet)
 for i,(title,v,bgcol) in enumerate([('旧稿：内凹切口和补片突起',before,None),('修后：补齐遮挡下的连续发面',after,None),('修后深底检查',after,'#253144')]):
  im=Image.fromarray(v).crop((450,400,650,790)).resize((350,682));bg=checker(im.size) if bgcol is None else Image.new('RGB',im.size,bgcol);bg.paste(im,(0,0),im);sheet.paste(bg,(i*440+45,60));d.text((i*440+10,20),title,font=font,fill='#26394c')
 sheet.save(OUT/'qa/left-cheek-upper-surface.jpg',quality=97)
 sheet=Image.new('RGB',(940,1080),'#e8edf3');d=ImageDraw.Draw(sheet)
 for i,(title,v) in enumerate([('旧左贴脸发检查稿',before),('上部补全后的检查稿',after)]):
  im=Image.fromarray(v).crop((410,130,820,1310));im.thumbnail((450,970));bg=checker((450,970));bg.paste(im,((450-im.width)//2,0),im);sheet.paste(bg,(i*470+10,55));d.text((i*470+10,16),title,font=font,fill='#26394c')
 d.text((15,1030),'实际透明发片；补画为隐藏面推断，尚未完成装配与动作验收。',font=font,fill='#52647a');sheet.save(OUT/'qa/left-cheek-upper-full.jpg',quality=97)
def prepare(source):
 ls={l.name:l for l in pixels(source)};a=full(ls['Cheek_L_LowerContour_LOCAL_REVIEW'])
 before=a.copy();yy,xx=np.indices(a.shape[:2]);rows=np.arange(2048)
 ry=[450,475,500,525,550,575,600,625,650,675,700,725,750,770]
 rx=[600,592,589,587,585,584,584,584,585,587,587,586,585.3,586.1]
 # Follow the existing interior hair line; retain it and repaint only its right.
 sy=[450,475,500,525,550,575,600,625,650,675,700,725,750,770]
 sx=[578,568,559,553,547,543,541,539,538,538,539,541,543,547]
 edge=PchipInterpolator(ry,rx,extrapolate=False)(rows)[:,None]
 spine=PchipInterpolator(sy,sx,extrapolate=False)(rows)[:,None]
 u=np.clip((xx-(spine+4))/(edge-(spine+4)),0,1)
 # Profiles from the same strand: gold near the upper root, pink shade below.
 def profile(y,x0,x1):
  samples=[]
  for dy in [-2,-1,0,1,2]:
   vals=np.stack([np.interp(np.linspace(x0,x1,256),np.arange(2048),a[y+dy,:,c]) for c in range(3)],axis=1);samples.append(vals)
  return gaussian_filter1d(np.median(samples,axis=0),2,axis=0)
 upper=profile(520,564,573);lower=profile(770,552,584.5)
 uv=np.nan_to_num(u);idx=np.minimum(np.rint(uv*255).astype('int32'),255)
 t=np.clip((yy-500)/270,0,1);t=t*t*(3-2*t)
 paint=upper[idx]*(1-t[:,:,None])+lower[idx]*t[:,:,None]
 # Feather joins in colour, not a transparent seam through the hair surface.
 weight=np.clip((xx-(spine+4))/4,0,1)*np.clip((yy-450)/35,0,1)*np.clip((770-yy)/15,0,1)
 weight=np.nan_to_num(weight);region=(yy>=450)&(yy<770)&(xx>=spine+4)&(xx<=edge+1)
 coverage=np.nan_to_num(np.clip(edge-xx+.5,0,1));wanted=np.rint(coverage*253).astype('uint8')
 new=a.copy();w=weight.copy();w[(a[:,:,3]<200)&region]=1
 rgb=np.rint(a[:,:,:3]*(1-w[:,:,None])+paint*w[:,:,None]).clip(0,255).astype('uint8');new[region,:3]=rgb[region]
 # Smooth contour at the repair band, retaining the interior alpha unchanged.
 contour=(yy>=450)&(yy<770)&(xx>=spine+4)
 new[contour,3]=wanted[contour]
 new[new[:,:,3]==0]=0
 for name,v in [('Cheek_L_before_upper_REVIEW',before),('Cheek_L_UpperSurface_LOCAL_REVIEW',new)]:Image.fromarray(v).save(OUT/'layers'/(name+'.png'))
 Image.fromarray((contour*255).astype('uint8')).save(OUT/'masks/upper_repair_region.png')
 Image.fromarray(np.rint(weight*255).astype('uint8')).save(OUT/'masks/colour_transition.png')
 changed=np.any(new!=before,axis=2);oldmask=before[:,:,3]>127;mask=new[:,:,3]>127;_,count=label(mask,np.ones((3,3)))
 oldholes=int((binary_fill_holes(oldmask)&~oldmask).sum());holes=int((binary_fill_holes(mask)&~mask).sum())
 assert np.array_equal(new[770:],before[770:]) and np.array_equal(new[:450],before[:450])
 assert np.array_equal(new[~contour],before[~contour])
 assert count==1 and holes==0
 records={'changed_review_pixels':int(changed.sum()),'added_alpha_pixels':int(((before[:,:,3]==0)&(new[:,:,3]>0)).sum()),'removed_alpha_pixels':int(((before[:,:,3]>0)&(new[:,:,3]==0)).sum()),'old_enclosed_alpha_hole_pixels':oldholes,'new_enclosed_alpha_hole_pixels':holes,'opaque_components':count,'lower_y_ge_770_exact':True,'upper_y_lt_450_exact':True,'outside_repair_mask_exact':True,'native_outer_curve':{'y':ry,'x':rx},'native_interior_line':{'y':sy,'x':sx},'colour_donor_profiles':[{'y':520,'x_start':564,'x_end':573},{'y':770,'x_start':552,'x_end':584.5}],'colour_sampling':'five-row median; 256-sample horizontal profiles; Gaussian sigma2; smoothstep along y','local_repaint_is_inferred_concealed_hair_not_recovered_original':True}
 preview(before,new)
 return new,records

def main(prepare_only=False):
 for name in ['layers','masks','qa']:(OUT/name).mkdir(parents=True,exist_ok=True)
 source=PSDImage.open(SOURCE);material,records=prepare(source)
 if prepare_only:print(json.dumps(records,indent=2));return
 original={l.name:l for l in pixels(source)};psd=PSDImage.new('RGBA',(2048,2048),color=0);clone(source,psd,psd,[])
 review=Group.new('15_LeftCheek_UpperSurface_REVIEW_OFF',parent=psd);review.visible=False
 name='Cheek_L_UpperSurface_LOCAL_REVIEW';add(psd,review,Image.fromarray(material),name)
 path=OUT/'Rurino_Left_Cheek_Upper_Surface_v034.psd';psd.save(path);saved=PSDImage.open(path);layers={l.name:l for l in pixels(saved)}
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
 report={'input_psd_sha256':sha(SOURCE),'saved_psd_sha256':sha(path),'pixel_layers':len(layers),'all_133_original_pixel_layers_and_properties_preserved':True,'new_layer_matches_png_after_save':True,'records':records,'states':states,'review_group_default_visible':False,'method':'smooth local hidden right silhouette; infer paint from same-strand gold/pink profiles; retain interior line and lower branches','limitations':['current left-view review material only; no new angle artwork','local concealed patch inferred from adjacent colours; not recovered original artwork; assembly and moving occlusion need validation','not a fully repainted hidden surface or a new runtime model','no Cubism mesh, keyforms, body motion or hair physics added'],'libtv_generation_used':False}
 (OUT/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--prepare-only',action='store_true');main(p.parse_args().prepare_only)
