"""Unify three-view material names and measure eye correspondence without warping.

The PSD is an editable reference assembly, not a Cubism model. The contour
sampler interpolates only within one view's blink guide anchors, never heads.
"""
import gc,hashlib,json,re
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageDraw,ImageFont
from psd_tools import PSDImage
from psd_tools.api.layers import Group,PixelLayer
from scipy.ndimage import gaussian_filter1d

ROOT=Path(__file__).resolve().parents[1];STAGE=ROOT/'rebuild_v3_4';TURN=STAGE/'turn_redraw';OUT=TURN/'eye_registration'
VIEWS={
 'Left':{'file':TURN/'side_blink_refinement/left/Rurino_Turn_Left_Blink_Materials_v034.psd','map':{'ImageLeft':'Far','ImageRight':'Near'},'nose':[780,942]},
 'Front':{'file':STAGE/'expression_refinement/Rurino_Head_Expression_Materials_v034.psd','map':{'ImageLeft':'L','ImageRight':'R'},'nose':[1024,957]},
 'Right':{'file':TURN/'side_blink_refinement/right/Rurino_Turn_Right_Blink_Materials_v034.psd','map':{'ImageLeft':'Near','ImageRight':'Far'},'nose':[1264,948]}}
STATES=['Open','Partial','Closed'];PARTS=['White','Iris','UpperLid','LowerLid'];BOX=(540,650,1510,1030)
FONT='/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc'
def font(size):return ImageFont.truetype(FONT,size)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n')
def pixels(g):
 for l in g:
  if l.is_group():yield from pixels(l)
  else:yield l

def state_of(name):
 for s in ['Open','Half','Closed']:
  if name.startswith('02_'+s) or '_Eyes_'+s+'_' in name:return 'Partial' if s=='Half' else s
 return None

def eye_of(view,name):
 if view=='Front':
  m=re.fullmatch(r'Eye_([LR])_(White|Iris|UpperLid|LowerLid)_(Open|Half|Closed)',name)
  if m:return ('ImageLeft' if m[1]=='L' else 'ImageRight',m[2],'Partial' if m[3]=='Half' else m[3])
 else:
  m=re.fullmatch(r'(Open|Half|Closed)_(Far|Near)_(White|Iris|UpperLid|LowerLid)',name)
  if m:return (next(k for k,v in VIEWS[view]['map'].items() if v==m[2]),m[3],'Partial' if m[1]=='Half' else m[1])
 return None

def original_name(view,eye,part,state):
 s='Half' if state=='Partial' else state;n=VIEWS[view]['map'][eye]
 return f'Eye_{n}_{part}_{s}' if view=='Front' else f'{s}_{n}_{part}'

def full_alpha(layer):
 a=np.zeros((2048,2048),np.uint8)
 if layer is None:return a
 im=layer.topil().convert('RGBA');x,y=layer.offset;a[y:y+im.height,x:x+im.width]=np.array(im)[:,:,3];return a

def poly_samples(alpha,xs):
 upper=[];lower=[]
 for x in xs:
  col=alpha[:,int(round(x))];ys=np.where(col>=128)[0]
  if len(ys):upper.append(float(ys[0]));lower.append(float(ys[-1]))
  else:upper.append(None);lower.append(None)
 return upper,lower

def eye_metrics(view,eye,lookup,hair):
 get=lambda part,state:lookup.get(original_name(view,eye,part,state))
 op=full_alpha(get('White','Open'));ha=full_alpha(get('White','Partial'));ir=full_alpha(get('Iris','Open'))
 ys,xs=np.where(op>=128);bbox=[int(xs.min()),int(ys.min()),int(xs.max()),int(ys.max())]
 iy,ix=np.where(ir>=128);cx=float(np.median(ix));cy=float(np.median(iy));columns=slice(round(cx)-2,round(cx)+3)
 phase=float(ha[:,columns].sum()/op[:,columns].sum());assert 0<phase<1
 # Use fixed source-view sample columns. These are visible aperture edges,
 # not recovered anatomical corners hidden behind hair/lashes.
 sample_x=np.linspace(bbox[0],bbox[2],21);ou,ol=poly_samples(op,sample_x);hu,hl=poly_samples(ha,sample_x)
 closed=full_alpha(get('UpperLid','Closed'));yy=np.arange(2048)[:,None]
 # Keep all pieces of the closing lash below the fold; largest-component
 # selection would discard legitimate pieces divided by the foreground hair.
 gate=int(bbox[1]+.38*(bbox[3]-bbox[1]));ink=closed.copy();ink[:gate]=0
 weights=ink.sum(0).astype('float64');valid=weights>255
 line=np.divide((ink*yy).sum(0),weights,out=np.zeros_like(weights),where=weights>0)
 xx=np.arange(2048);line=np.interp(xx,xx[valid],line[valid]);line=gaussian_filter1d(line,1)
 closure=[round(float(np.interp(x,xx,line)),3) for x in sample_x]
 for i in range(len(sample_x)):
  if ou[i] is None:ou[i]=ol[i]=closure[i]
  if hu[i] is None:hu[i]=hl[i]=closure[i]
 # Hash the source iris texture and placement: partial blink must cover the
 # same eye texture instead of moving it to fake changing eye spacing.
 a=get('Iris','Open');b=get('Iris','Partial');assert a.offset==b.offset and np.array_equal(np.array(a.topil()),np.array(b.topil()))
 masks={};occ={}
 for state,ap in [('Open',op),('Partial',ha)]:
  masks[state]=ap
  total=float(ap.sum());occ[state]={'aperture_alpha_area':total/255,'foreground_overlap_alpha_area':float((ap.astype('float64')*hair/255).sum()/255)}
 inner_side='right' if eye=='ImageLeft' else 'left'
 def end(mark):
  k=-1 if mark=='right' else 0;return [round(float(sample_x[k]),3),round((ou[k]+ol[k])/2,3)]
 return {'canonical_eye':eye,'source_alias':VIEWS[view]['map'][eye],
 'visible_aperture_bbox':bbox,'visible_inner_boundary':end(inner_side),'visible_outer_boundary':end('left' if inner_side=='right' else 'right'),
 'corner_semantics':'visible white-aperture endpoints only; anatomical canthi behind lashes/hair are unresolved',
 'iris_reference_center':[cx,cy],'iris_offset':list(a.offset),'iris_texture_sha256':hashlib.sha256(a.topil().tobytes()).hexdigest(),'iris_identical_open_partial':True,
 'partial_center_height_ratio':phase,'partial_area_ratio':float(ha.sum()/op.sum()),
 'blink_guide_anchor_positions':{'Closed':0.0,'Partial':phase,'Open':1.0},
 'guide_definition':'local aperture height relative to this view at the fixed open-iris X; a guide coordinate, not a bound Cubism parameter',
 'contours':{'x':[round(float(x),3) for x in sample_x],'Open':{'upper':ou,'lower':ol},'Partial':{'upper':hu,'lower':hl},'Closed':{'upper':closure,'lower':closure}},
 'closure_line_definition':'alpha-weighted center of rendered closing lash after fold exclusion; not an anatomical lid junction',
 'occlusion':occ}

def sample_blink(record,openness):
 """A monotone per-view contour guide. No texture or head deformation."""
 p=float(openness)
 if not 0<=p<=1:raise ValueError('openness must be within [0, 1]')
 mid=record['partial_center_height_ratio'];lo,hi=('Closed','Partial') if p<=mid else ('Partial','Open')
 t=p/mid if p<=mid else (p-mid)/(1-mid)
 curves=record['contours'];out={'openness':p,'source_segment':[lo,hi],'segment_fraction':t,'x':curves['x']}
 for key in ['upper','lower']:
  out[key]=((1-t)*np.array(curves[lo][key])+t*np.array(curves[hi][key])).tolist()
 assert np.all(np.array(out['lower'])>=np.array(out['upper']))
 return out

def clone_group(source,parent,target,view,mapping,path=''):
 for item in source:
  original_path=path+'/'+item.name
  if item.is_group():
   state=state_of(item.name)
   name=(f'Blink_{state}'+('_ART_ANCHOR_SEE_MAP' if state=='Partial' else '')) if state else item.name
   g=Group.new(name,parent=parent);g.visible=item.visible;g.opacity=item.opacity
   if item.blend_mode is not None:g.blend_mode=item.blend_mode
   clone_group(item,g,target,view,mapping,original_path)
  else:
   semantic=eye_of(view,item.name)
   name=view+'_'+('_'.join([semantic[0],semantic[2],semantic[1]]) if semantic else item.name)
   im=item.topil().convert('RGBA');layer=PixelLayer.frompil(im,psd_file=target,layer_name=name,top=item.top,left=item.left)
   parent.append(layer);layer.visible=item.visible;layer.opacity=item.opacity;layer.clipping_layer=item.clipping_layer
   if item.blend_mode is not None:layer.blend_mode=item.blend_mode
   mapping.append({'view':view,'source_path':original_path,'source_name':item.name,'target_name':name,'offset':list(item.offset),'dimensions':list(im.size),'rgba_sha256':hashlib.sha256(im.tobytes()).hexdigest(),'clipping':bool(item.clipping_layer),'eye_semantics':list(semantic) if semantic else None})

def draw_guide(view,metrics):
 im=Image.new('RGBA',(2048,2048));d=ImageDraw.Draw(im)
 colors={'ImageLeft':(20,190,235,235),'ImageRight':(240,145,35,235)}
 for eye,r in metrics.items():
  color=colors[eye];x=r['contours']['x']
  for key in ['upper','lower']:d.line(list(zip(x,r['contours']['Open'][key])),fill=color,width=3)
  d.line(list(zip(x,r['contours']['Closed']['upper'])),fill=(190,80,210,230),width=3)
  for k in ['visible_inner_boundary','visible_outer_boundary']:
   px,py=r[k];d.ellipse((px-6,py-6,px+6,py+6),outline=color,width=3)
  cx,cy=r['iris_reference_center'];d.line((cx-8,cy,cx+8,cy),fill=color,width=2);d.line((cx,cy-8,cx,cy+8),fill=color,width=2)
 nx,ny=VIEWS[view]['nose'];d.line((nx-10,ny,nx+10,ny),fill=(235,70,70,255),width=3);d.line((nx,ny-10,nx,ny+10),fill=(235,70,70,255),width=3)
 return im

def main():
 for folder in ['qa','guides','source-renders']:(OUT/folder).mkdir(parents=True,exist_ok=True)
 atlas=PSDImage.new('RGBA',(2048,2048),color=0);mapping=[];views={};guides={}
 for view,config in VIEWS.items():
  source=PSDImage.open(config['file']);lookup={l.name:l for l in pixels(source)}
  root=Group.new('View_'+view+'_SHOW_ONE_VIEW_ONLY',parent=atlas);root.visible=view=='Front';clone_group(source,root,atlas,view,mapping)
  # Extract foreground coverage from actual saved layers, excluding brows.
  hair=np.zeros((2048,2048),np.float64)
  items=[l for l in pixels(source) if (view!='Front' and l.name=='Foreground_Hair_Overlap') or (view=='Front' and l.parent.name=='06_Foreground_Hair_and_Brows' and not l.name.startswith('Brow_'))]
  for l in items:a=full_alpha(l)/255;hair=1-(1-hair)*(1-a)
  hair=np.rint(hair*255).astype('uint8')
  eyes={eye:eye_metrics(view,eye,lookup,hair) for eye in ['ImageLeft','ImageRight']};guide=draw_guide(view,eyes);guides[view]=guide;guide.save(OUT/'guides'/f'{view.lower()}-correspondence.png')
  span=eyes['ImageRight']['iris_reference_center'][0]-eyes['ImageLeft']['iris_reference_center'][0]
  gap=eyes['ImageRight']['visible_aperture_bbox'][0]-eyes['ImageLeft']['visible_aperture_bbox'][2]
  nx,ny=config['nose'];centers=np.array([eyes[e]['iris_reference_center'] for e in eyes])
  views[view]={'source_file':str(config['file'].relative_to(ROOT)),'source_sha256':sha(config['file']),'source_layer_count':len(lookup),'nose_mark_manual':config['nose'],'eyes':eyes,
   'eye_pair':{'iris_x_separation_px':span,'visible_aperture_gap_px':gap,'nose_offset_over_iris_span':float((nx-centers[:,0].mean())/span)},
   'guide_samples':{eye:[sample_blink(rec,p) for p in [0,.25,.5,.75,1]] for eye,rec in eyes.items()}}
  for state in STATES:
   for g in source:
    if state_of(g.name):g.visible=state_of(g.name)==state
   source.composite(force=True).save(OUT/'source-renders'/f'{view.lower()}-{state.lower()}.png')
  del source;gc.collect()
 g=Group.new('Guides_NOT_MODEL_PARTS_HIDDEN',parent=atlas);g.visible=False
 for view,im in guides.items():
  l=PixelLayer.frompil(im,psd_file=atlas,layer_name='Guide_'+view,top=0,left=0);g.append(l);l.visible=view=='Front'
 path=OUT/'Rurino_Three_View_Eye_Assembly_v034.psd';atlas.save(path);del atlas;gc.collect()
 report={'scope':'three-view editable source assembly and blink contour correspondence; not geometrically registered head or Cubism rig',
 'coordinate_system':'original 2048x2048 pixels; no image translation, scale, mirror or head warp',
 'eye_naming':'ImageLeft/ImageRight refer to viewer coordinates, stable identities across these limited yaw views; old front L/R were screen-side labels',
 'view_mapping':{v:c['map'] for v,c in VIEWS.items()},'views':views,'layer_map':mapping,
 'art_layers':len(mapping),'guide_layers':3,'psd_sha256':sha(path),
 'limits':['visible aperture endpoints are not hidden anatomical corners','iris references follow original gaze, not orbit centers','Partial artwork is NOT a universal 0.5 blink key','contour guides are preliminary interpolation targets, not meshes or visible animation','original view scale/neck registration and concealed lid/hair structure remain unresolved']}
 dump(OUT/'correspondence.json',report);dump(OUT/'blink-guide-samples.json',{v:r['guide_samples'] for v,r in views.items()})
 print(json.dumps({'art_layers':len(mapping),'guide_layers':3,'partial_phases':{v:{e:round(r['partial_center_height_ratio'],4) for e,r in d['eyes'].items()} for v,d in views.items()},'psd':str(path)},indent=2))
if __name__=='__main__':main()
