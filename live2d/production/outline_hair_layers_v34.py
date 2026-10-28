"""Give each independent hair material its own editable black contour layer.
Source colours, alpha silhouettes and non-hair pixels are preserved verbatim.
This is a layered raster material edit, not a Cubism rig or a generated image.
"""
import argparse,gc,hashlib,json
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
from psd_tools import PSDImage
from psd_tools.api.layers import Group,PixelLayer
ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'rebuild_v3_4/turn_redraw/whole_hair_static_completion/Rurino_Whole_Hair_Static_v034.psd'
OUT=ROOT/'rebuild_v3_4/turn_redraw/hair_independent_ink'
PSD=OUT/'Rurino_Hair_Independent_Ink_v034.psd'
FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
W,H,DX=3456,2816,704
WIDTHS={'Crown':2.8,'Cheek_L':2.5,'Cheek_R':2.5,'Small_L':2.8,'Small_R':2.8,'Temple_R':2.2,'Large_L':3.4,'Large_R':3.4,'Thin_R':2.0}
ORDER=['Crown','Cheek_L','Cheek_R','Small_L','Small_R','Temple_R','Large_L','Large_R','Thin_R']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pixels(g):
 for l in g:
  if l.is_group():yield from pixels(l)
  else:yield l

def copy_pixel(l,parent,psd):
 n=PixelLayer.frompil(l.topil().convert('RGBA'),psd_file=psd,layer_name=l.name,top=l.top,left=l.left);parent.append(n)
 n.visible=l.visible;n.opacity=l.opacity;n.clipping_layer=l.clipping_layer
 if l.blend_mode is not None:n.blend_mode=l.blend_mode
 return n

def ink_image(im,width,name,offset):
 # Existing artist lines and genuinely new contour sections share one black
 # ink layer. Snap near existing dark strokes rather than draw a parallel line.
 a=np.array(im.convert('RGBA'));alpha=a[:,:,3];h,w=alpha.shape
 up=np.array(Image.fromarray(alpha).resize((w*3,h*3),Image.Resampling.LANCZOS))
 # Slight contour smoothing removes single-pixel tracing teeth, not forks.
 up=cv2.GaussianBlur(up,(0,0),1.4)
 inside=(up>127).astype('uint8');dist=cv2.distanceTransform(np.pad(inside,1),cv2.DIST_L2,5)[1:-1,1:-1]/3-.1667
 coverage=np.clip((width+.45-dist)/.9,0,1)*inside
 base=np.array(Image.fromarray(np.rint(coverage*235).astype('uint8')).resize((w,h),Image.Resampling.LANCZOS)).astype(float)
 depth=cv2.distanceTransform((alpha>127).astype('uint8'),cv2.DIST_L2,5)
 rgb=a[:,:,:3].astype(float);lum=rgb[:,:,0]*.30+rgb[:,:,1]*.59+rgb[:,:,2]*.11
 darkness=np.clip((185-lum)/45,0,1)*(alpha>127)*(depth<11)
 # The blue/lavender surface shading is not a black line.
 darkness*=rgb[:,:,2]<rgb[:,:,0]+40
 seeds=darkness>.32
 near=cv2.distanceTransform((~seeds).astype('uint8'),cv2.DIST_L2,5)
 base*=np.clip((near-4.5)/2,0,1)
 # Shared upper roots overlap the other front hair plates. Their construction
 # cut is not a free hair edge; retain the source flow line there, without a
 # black closure across the forehead or across the top of the cheek lock.
 yy,xx=np.indices((h,w));yy=yy+offset[1];xx=xx+offset[0]-DX
 gate=np.ones((h,w),float)
 if name=='Crown':
  zones=((xx>1190)&(yy>190)&(yy<650))|((xx<750)&(yy>230)&(yy<740))|((xx>780)&(xx<950)&(yy>290)&(yy<440))
  gate[zones]=0
 elif name in ['Cheek_L','Cheek_R','Temple_R']:
  end={'Cheek_L':730,'Cheek_R':580,'Temple_R':650}[name];gate=np.clip((yy-(end-90))/90,0,1)
 elif name=='Thin_R':gate=np.clip((yy-1010)/90,0,1)
 # Feather the root selection so no line ends at a square boundary.
 gate=cv2.GaussianBlur(gate,(0,0),8)
 base*=gate
 existing=darkness*225*np.clip((7-near)/3,0,1)
 aa=cv2.GaussianBlur(np.maximum(base,existing),(0,0),.35);aa=np.minimum(np.rint(aa).clip(0,235).astype('uint8'),alpha);aa[alpha==0]=0
 ink=np.zeros_like(a);ink[:,:,3]=aa
 return Image.fromarray(ink)

def paste_full(im,offset):
 out=Image.new('RGBA',(W,H));out.paste(im,offset);return out

def tiled(psd):
 out=Image.new('RGBA',(W,H))
 for y in range(0,H,704):
  for x in range(0,W,864):
   b=(x,y,min(x+864,W),min(y+704,H));out.paste(psd.composite(viewport=b,force=True,color=(0,0,0),alpha=0),(x,y))
 return out

def set_state(doc,state):
 for g in doc:
  if g.name.startswith('02_'):g.visible=g.name=='02_'+state

def checker(size):
 a=Image.new('RGB',size,'#edf0f4');d=ImageDraw.Draw(a)
 for y in range(0,size[1],20):
  for x in range(0,size[0],20):
   if (x//20+y//20)%2==0:d.rectangle((x,y,x+19,y+19),fill='#ccd5df')
 return a

def previews():
 font=ImageFont.truetype(FONT,23);small=ImageFont.truetype(FONT,19)
 a=Image.open(OUT/'qa/ink-assembled-Open.png')
 im=a.crop((DX+280,45,DX+1740,1400));im.thumbnail((1000,1000));bg=checker(im.size);bg.paste(im,(0,0),im);bg.save(OUT/'qa/hair-ink-head.jpg',quality=97)
 im=a.copy();im.thumbnail((1060,870));bg=Image.new('RGB',(1100,960),'#27313f');bg.paste(im,((1100-im.width)//2,50),im);d=ImageDraw.Draw(bg);d.text((25,15),'每片头发独立黑线 · 静态装配',font=font,fill='white');d.text((25,925),'黑线与颜色可分别开关；尚未绑定 Cubism 动作。',font=small,fill='#cedbea');bg.save(OUT/'qa/hair-ink-assembly.jpg',quality=96)
 sheet=Image.new('RGB',(1500,1740),'#e8edf3');d=ImageDraw.Draw(sheet)
 for i,n in enumerate(ORDER):
  im=Image.open(OUT/'merged-hair'/(n+'.png'));im=im.crop(im.getbbox());im.thumbnail((480,515));bg=checker((480,515));bg.paste(im,((480-im.width)//2,(515-im.height)//2),im);x=i%3*500;y=i//3*580;sheet.paste(bg,(x+10,y+50));d.text((x+15,y+15),n+' · 独立黑色轮廓',font=small,fill='#26394c')
 sheet.save(OUT/'qa/hair-ink-components.jpg',quality=96)
 sheet=Image.new('RGB',(1500,660),'#e8edf3');d=ImageDraw.Draw(sheet)
 for i,state in enumerate(['Open','Half','Closed']):
  im=Image.open(OUT/'qa'/('ink-assembled-'+state+'.png')).crop((DX+280,40,DX+1740,1370));im.thumbnail((490,550));bg=checker((490,550));bg.paste(im,((490-im.width)//2,0),im);sheet.paste(bg,(i*500+5,55));d.text((i*500+15,15),{'Open':'睁眼','Half':'半闭眼','Closed':'闭眼'}[state],font=font,fill='#26394c')
 sheet.save(OUT/'qa/hair-ink-eye-states.jpg',quality=96)
 # Large root/tip close-ups to inspect real strokes, not just a thumbnail.
 sheet=Image.new('RGB',(1400,860),'#e8edf3');d=ImageDraw.Draw(sheet)
 boxes=[('Small_L',(DX+360,350,DX+630,750)),('Large_L',(DX-245,2180,DX+275,2590)),('Crown',(DX+1100,150,DX+1500,550))]
 for i,(n,box) in enumerate(boxes):
  for row,folder in enumerate(['colour','merged-hair']):
   im=Image.open(OUT/folder/(n+'.png')).crop(box);im.thumbnail((450,355));bg=checker((450,355));bg.paste(im,((450-im.width)//2,0),im);sheet.paste(bg,(i*465+10,row*420+50));d.text((i*465+12,row*420+15),n+(' · 原素材' if row==0 else ' · 独立黑线开启'),font=small,fill='#26394c')
 sheet.save(OUT/'qa/hair-ink-detail-comparison.jpg',quality=96)

def main():
 for n in ['colour','ink','merged-hair','qa']:(OUT/n).mkdir(parents=True,exist_ok=True)
 source=PSDImage.open(SOURCE);old={l.name:l for l in pixels(source)};ink={};records=[]
 for n,width in WIDTHS.items():
  layer=old[n];im=layer.topil().convert('RGBA');line=ink_image(im,width,n,layer.offset);ink[n]=line
  paste_full(im,layer.offset).save(OUT/'colour'/(n+'.png'));paste_full(line,layer.offset).save(OUT/'ink'/('Ink_'+n+'.png'))
  # Export combined per-part PNGs without changing the colour-layer source.
  merged=Image.alpha_composite(im,line);paste_full(merged,layer.offset).save(OUT/'merged-hair'/(n+'.png'))
  a=np.array(im);b=np.array(line);assert np.all(b[:,:,:3]==0);assert not np.any(b[a[:,:,3]==0,3])
  records.append({'part':n,'ink_layer':'Ink_'+n,'native_stroke_px':width,'rgb':[0,0,0],'max_alpha':235,'ink_pixels':int((b[:,:,3]>0).sum()),'ink_inside_original_alpha':True,'align_to_existing_dark_strokes':True,'shared_root_line_fade':n in ['Crown','Cheek_L','Cheek_R','Temple_R','Thin_R']})
 psd=PSDImage.new('RGBA',(W,H),color=0)
 def clone(items,parent):
  for item in items:
   if item.is_group():
    g=Group.new(item.name,parent=parent);g.visible=item.visible;g.opacity=item.opacity
    if item.blend_mode is not None:g.blend_mode=item.blend_mode
    clone(item,g)
   elif item.name in ink:
    g=Group.new(item.name+'__Colour_and_Ink',parent=parent);copy_pixel(item,g,psd)
    new=PixelLayer.frompil(ink[item.name],psd_file=psd,layer_name='Ink_'+item.name,top=item.top,left=item.left);g.append(new)
   else:copy_pixel(item,parent,psd)
 clone(source,psd)
 # Existing source foreground pieces sit above the eyes. Restore only the
 # SAME parent outline where that foreground gold would otherwise cover it.
 fg=next(g for g in psd if g.name=='03_Hair_Over_Eyes_Preserved');overlap_records=[]
 for originalname,parentname in [('Left_Cheek_EyeOverlap_SOURCE','Cheek_L'),('Left_Fringe_EyeOverlap_SOURCE','Crown'),('RightFringe_ForegroundTips_SOURCE','Crown')]:
  original=old[originalname];parent=old[parentname];b=np.array(paste_full(ink[parentname],parent.offset));m=np.array(paste_full(original.topil().convert('RGBA'),original.offset))[:,:,3]
  b[:,:,3]=np.rint(b[:,:,3].astype(float)*m/255).astype('uint8');im=Image.fromarray(b);box=im.getbbox()
  if box:
   n='Ink_Overlap_'+originalname;new=PixelLayer.frompil(im.crop(box),psd_file=psd,layer_name=n,top=box[1],left=box[0]);fg.append(new);im.save(OUT/'ink'/(n+'.png'));overlap_records.append({'name':n,'parent_ink':'Ink_'+parentname,'source_mask':originalname})
 set_state(psd,'Open');default=tiled(psd);default.save(OUT/'qa/ink-assembled-Open.png');print('Rendered default',flush=True)
 psd._update_record();psd._record.image_data.set_data([ch.tobytes() for ch in default.split()],psd._record.header)
 with PSD.open('wb') as f:psd._record.write(f)
 del psd;gc.collect();saved=PSDImage.open(PSD);new={l.name:l for l in pixels(saved)}
 for n,l in old.items():
  target=new[n];assert np.array_equal(np.array(l.topil().convert('RGBA')),np.array(target.topil().convert('RGBA'))),n
  assert l.offset==target.offset,n
  assert (l.visible,l.opacity,l.blend_mode,l.clipping_layer)==(target.visible,target.opacity,target.blend_mode,target.clipping_layer),n
 for n in WIDTHS:assert np.array_equal(np.array(new['Ink_'+n].topil().convert('RGBA')),np.array(ink[n]))
 for record in overlap_records:
  n=record['name'];im=Image.open(OUT/'ink'/(n+'.png')).convert('RGBA');box=im.getbbox();assert tuple(new[n].bbox)==tuple(box)
  assert np.array_equal(np.array(new[n].topil().convert('RGBA')),np.array(im.crop(box)))
 for n,l in new.items():
  if n.startswith('Ink_'):assert np.all(np.array(l.topil().convert('RGBA'))[:,:,:3]==0)
 assert np.array_equal(np.array(tiled(saved)),np.array(default));print('Verified original pixels, saved ink and default preview',flush=True)
 # Turning off every new ink layer must restore the exact previous PSD view.
 for l in pixels(saved):
  if l.name.startswith('Ink_'):l.visible=False
 base=tiled(saved);expected=tiled(source);assert np.array_equal(np.array(base),np.array(expected))
 for l in pixels(saved):
  if l.name.startswith('Ink_'):l.visible=True
 states=[]
 for state in ['Open','Half','Closed']:
  set_state(saved,state);im=default if state=='Open' else tiled(saved);im.save(OUT/'qa'/('ink-assembled-'+state+'.png'));states.append({'state':state,'sha256':sha(OUT/'qa'/('ink-assembled-'+state+'.png'))});print('Rendered',state,flush=True)
 r={'source_psd':str(SOURCE.relative_to(ROOT)),'source_sha256':sha(SOURCE),'psd':PSD.name,'sha256':sha(PSD),'canvas':[W,H],'pixel_layers':len(new),'original_layers_preserved':len(old),'original_rgba_offsets_properties_exact':True,'ink_layers':records,'foreground_ink_carryovers':overlap_records,'ink_off_matches_previous_default_exact':True,'saved_default_matches_preview_exact':True,'all_added_ink_layers_roundtrip_exact':True,'states':states,'scope':'independent hair contours only; no Cubism rig added','black_stroke_mode':'inward 3x antialiased contour with existing-line alignment and shared-root fades; editable black pixels, separate from original colour layers'}
 (OUT/'verification.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');previews();print(json.dumps({'psd':str(PSD),'layers':len(new),'hair_parts':len(WIDTHS),'preserved':len(old)},indent=2))
if __name__=='__main__':main()
